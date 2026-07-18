#!/usr/bin/env python3
"""Benchmark exact M=4/M=8 TP4+MHC geometry from a captured corpus.

This is a component economics gate, not a model-throughput or acceptance test.
The historical default tiles rows from the captured real M=2 verifier pair.
``--source-width`` also permits direct replay of genuine sequential M=4/M=8
captures.  MHC is tested as row-exact M=2 chunks, one fixed-width command, and
through the existing arbitrary-M fused operator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import time
from typing import Any, Callable

import torch
import torch.distributed as dist
import vllm_xpu_kernels._C  # noqa: F401
import vllm_xpu_kernels._xpu_C as xpu_extension


ALLREDUCES = 87
MHC_BOUNDARIES = 85
OUTPUT_NAMES = (
    "residual_out",
    "next_post_mix",
    "next_comb_mix",
    "layer_input",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_rows(root: Path, rank: int, category: str, expected: int) -> list[dict[str, Any]]:
    paths = sorted((root / f"rank{rank}" / category).glob("*.json"))
    if len(paths) != expected:
        raise ValueError(f"rank {rank} {category}: expected {expected}, got {len(paths)}")
    return [json.loads(path.read_text()) for path in paths]


def tile_rows(tensor: torch.Tensor, width: int) -> torch.Tensor:
    if tensor.ndim == 0 or tensor.shape[0] != 2:
        raise ValueError(f"cannot row-tile shape {tuple(tensor.shape)}")
    return torch.cat([tensor] * (width // 2), dim=0).contiguous()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--width", type=int, choices=(4, 8), required=True)
    parser.add_argument("--source-width", type=int, choices=(2, 4, 8), default=2)
    parser.add_argument(
        "--path",
        choices=(
            "segmented_m2",
            "segmented_fixed_width",
            "m2_chunks",
            "fixed_width",
            "generic_fused",
        ),
        required=True,
    )
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--changed-eager-epochs", type=int, default=16)
    parser.add_argument("--warmup", type=int, default=4)
    parser.add_argument("--exact-replays", type=int, default=70)
    parser.add_argument("--timed-replays", type=int, default=20)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rank = int(os.environ["RANK"])
    local_rank = int(os.environ["LOCAL_RANK"])
    world_size = int(os.environ["WORLD_SIZE"])
    if world_size != 4:
        raise ValueError(f"requires world_size=4, got {world_size}")
    torch.xpu.set_device(local_rank)
    device = torch.device(f"xpu:{local_rank}")
    dist.init_process_group(backend="xccl", device_id=device)

    root = args.corpus.resolve()
    if args.source_width > args.width or args.width % args.source_width:
        raise ValueError(
            f"source width {args.source_width} cannot produce width {args.width}"
        )
    allreduce_rows = load_rows(
        root, rank, f"allreduce_m{args.source_width}", ALLREDUCES
    )
    mhc_rows = load_rows(
        root, rank, f"mhc_post_pre_m{args.source_width}", MHC_BOUNDARIES
    )
    cpu_cache: dict[str, torch.Tensor] = {}
    device_cache: dict[str, torch.Tensor] = {}

    def get_tensor(ref: dict[str, Any]) -> torch.Tensor:
        relative = ref["blob"]
        if relative not in device_cache:
            if relative not in cpu_cache:
                cpu_cache[relative] = torch.load(
                    root / relative, map_location="cpu", weights_only=True
                )
            device_cache[relative] = cpu_cache[relative].to(device)
        return device_cache[relative]

    def wide_tensor(ref: dict[str, Any]) -> torch.Tensor:
        tensor = get_tensor(ref)
        if args.source_width == args.width:
            if tensor.ndim == 0 or tensor.shape[0] != args.width:
                raise ValueError(
                    f"expected direct M={args.width} tensor, got {tuple(tensor.shape)}"
                )
            return tensor
        if args.source_width != 2:
            raise ValueError("only the historical M=2 corpus may be row-tiled")
        return tile_rows(tensor, args.width)

    local_partial = [
        wide_tensor(row["tensors"]["local_partial"]) for row in allreduce_rows
    ]
    expected_reduced = [
        wide_tensor(row["tensors"]["reduced"]) for row in allreduce_rows
    ]

    def mhc_input(name: str, *, tiled: bool = True) -> list[torch.Tensor]:
        values = [get_tensor(row["tensors"][name]) for row in mhc_rows]
        return [wide_tensor(row["tensors"][name]) for row in mhc_rows] if tiled else values

    residual = mhc_input("residual")
    post_mix = mhc_input("post_mix")
    comb_res_mix = mhc_input("comb_res_mix")
    fn = mhc_input("fn", tiled=False)
    hc_scale = mhc_input("hc_scale", tiled=False)
    hc_base = mhc_input("hc_base", tiled=False)
    expected_outputs = {name: mhc_input(name) for name in OUTPUT_NAMES}
    row_inputs = [
        *local_partial,
        *expected_reduced,
        *residual,
        *post_mix,
        *comb_res_mix,
        *(tensor for values in expected_outputs.values() for tensor in values),
    ]
    canonical_row_inputs = [tensor.clone() for tensor in row_inputs]

    def apply_changed_input_schedule(replay: int) -> None:
        pattern = replay % (1 << (args.width // 2))
        order = []
        for tile in range(args.width // 2):
            pair = [tile * 2, tile * 2 + 1]
            if pattern & (1 << tile):
                pair.reverse()
            order.extend(pair)
        row_order = torch.tensor(order, dtype=torch.int64, device=device)
        for target, canonical in zip(row_inputs, canonical_row_inputs, strict=True):
            target.copy_(canonical.index_select(0, row_order))
        synchronize()

    def synchronize() -> None:
        torch.xpu.synchronize(device)

    def build_path(
        kind: str,
    ) -> tuple[Callable[[], None], Callable[[], None], dict[str, Any]]:
        reduced = [torch.empty_like(tensor) for tensor in expected_reduced]
        outputs = {
            name: [torch.empty_like(tensor) for tensor in tensors]
            for name, tensors in expected_outputs.items()
        }
        witnesses = [
            torch.empty(1, dtype=torch.bfloat16, device=device)
            for _ in range(MHC_BOUNDARIES)
        ]

        def run_mhc(boundary: int, x: torch.Tensor) -> None:
            if kind in ("segmented_m2", "m2_chunks"):
                for start in range(0, args.width, 2):
                    stop = start + 2
                    torch.ops._xpu_C.mhc_post_pre_m2_out(
                            x[start:stop],
                            residual[boundary][start:stop],
                            post_mix[boundary][start:stop],
                            comb_res_mix[boundary][start:stop],
                            fn[boundary],
                            hc_scale[boundary],
                            hc_base[boundary],
                            outputs["residual_out"][boundary][start:stop],
                            outputs["next_post_mix"][boundary][start:stop],
                            outputs["next_comb_mix"][boundary][start:stop],
                            outputs["layer_input"][boundary][start:stop],
                            mhc_rows[boundary]["rms_eps"],
                            mhc_rows[boundary]["hc_eps"],
                            mhc_rows[boundary]["hc_eps"],
                            mhc_rows[boundary]["hc_post_alpha"],
                            mhc_rows[boundary]["sinkhorn_iters"],
                    )
            elif kind in ("segmented_fixed_width", "fixed_width"):
                fixed_op = getattr(
                    torch.ops._xpu_C,
                    f"mhc_post_pre_m{args.width}_out",
                )
                fixed_op(
                        x,
                        residual[boundary],
                        post_mix[boundary],
                        comb_res_mix[boundary],
                        fn[boundary],
                        hc_scale[boundary],
                        hc_base[boundary],
                        outputs["residual_out"][boundary],
                        outputs["next_post_mix"][boundary],
                        outputs["next_comb_mix"][boundary],
                        outputs["layer_input"][boundary],
                        mhc_rows[boundary]["rms_eps"],
                        mhc_rows[boundary]["hc_eps"],
                        mhc_rows[boundary]["hc_eps"],
                        mhc_rows[boundary]["hc_post_alpha"],
                        mhc_rows[boundary]["sinkhorn_iters"],
                )
            elif kind == "generic_fused":
                actual = torch.ops._xpu_C.mhc_fused_post_pre(
                        x,
                        residual[boundary],
                        post_mix[boundary],
                        comb_res_mix[boundary],
                        fn[boundary],
                        hc_scale[boundary],
                        hc_base[boundary],
                        mhc_rows[boundary]["rms_eps"],
                        mhc_rows[boundary]["hc_eps"],
                        mhc_rows[boundary]["hc_eps"],
                        mhc_rows[boundary]["hc_post_alpha"],
                        mhc_rows[boundary]["sinkhorn_iters"],
                )
                for name, tensor in zip(OUTPUT_NAMES, actual, strict=True):
                    outputs[name][boundary] = tensor
            else:
                raise AssertionError(kind)
            witnesses[boundary].copy_(
                outputs["layer_input"][boundary].reshape(-1)[:1]
            )

        def changed_eager_mhc() -> None:
            for boundary in range(MHC_BOUNDARIES):
                run_mhc(boundary, expected_reduced[boundary + 1])

        def cycle() -> None:
            for collective in range(ALLREDUCES):
                if kind in ("segmented_m2", "segmented_fixed_width"):
                    for start in range(0, args.width, 2):
                        stop = start + 2
                        reduced[collective][start:stop].copy_(
                            local_partial[collective][start:stop]
                        )
                        dist.all_reduce(reduced[collective][start:stop])
                else:
                    reduced[collective].copy_(local_partial[collective])
                    dist.all_reduce(reduced[collective])
                if 1 <= collective <= MHC_BOUNDARIES:
                    run_mhc(collective - 1, reduced[collective])

        return cycle, changed_eager_mhc, {"reduced": reduced, "outputs": outputs}

    def run_path(kind: str) -> dict[str, Any]:
        cycle, changed_eager_mhc, state = build_path(kind)

        def mismatch_counts() -> tuple[int, dict[str, int]]:
            reduced_mismatches = sum(
                int((actual != expected).sum().item())
                for actual, expected in zip(
                    state["reduced"], expected_reduced, strict=True
                )
            )
            output_mismatches = {
                name: sum(
                    int((actual != expected).sum().item())
                    for actual, expected in zip(
                        state["outputs"][name], expected_outputs[name], strict=True
                    )
                )
                for name in OUTPUT_NAMES
            }
            return reduced_mismatches, output_mismatches

        changed_eager_rows = []
        for epoch in range(args.changed_eager_epochs):
            apply_changed_input_schedule(epoch)
            changed_eager_mhc()
            synchronize()
            _, output_mismatches = mismatch_counts()
            changed_eager_rows.append(
                {
                    "epoch": epoch,
                    "schedule": epoch % (1 << (args.width // 2)),
                    "reduced_mismatches": 0,
                    "output_mismatches": output_mismatches,
                }
            )

        apply_changed_input_schedule(0)
        for collective in range(ALLREDUCES):
            if kind in ("segmented_m2", "segmented_fixed_width"):
                for start in range(0, args.width, 2):
                    stop = start + 2
                    state["reduced"][collective][start:stop].copy_(
                        local_partial[collective][start:stop]
                    )
                    synchronize()
                    dist.all_reduce(state["reduced"][collective][start:stop])
                    synchronize()
            else:
                state["reduced"][collective].copy_(local_partial[collective])
                synchronize()
                dist.all_reduce(state["reduced"][collective])
                synchronize()
        collective_eager_mismatches = sum(
            int((actual != expected).sum().item())
            for actual, expected in zip(
                state["reduced"], expected_reduced, strict=True
            )
        )
        collective_eager_row_mismatches = [
            sum(
                int((actual[row] != expected[row]).sum().item())
                for actual, expected in zip(
                    state["reduced"], expected_reduced, strict=True
                )
            )
            for row in range(args.width)
        ]
        collective_eager_row_matches_local = [
            sum(
                int((actual[row] == local[row]).all().item())
                for actual, local in zip(
                    state["reduced"], local_partial, strict=True
                )
            )
            for row in range(args.width)
        ]
        collective_eager_duplicate_row_mismatches = [
            {
                "rows": [row, row + 2],
                "mismatches": sum(
                    int((actual[row] != actual[row + 2]).sum().item())
                    for actual in state["reduced"]
                ),
            }
            for row in range(args.width - 2)
        ]
        collective_eager_max_abs_diff = max(
            float((actual.float() - expected.float()).abs().max().item())
            for actual, expected in zip(
                state["reduced"], expected_reduced, strict=True
            )
        )
        collective_eager_passed = collective_eager_mismatches == 0

        # XPUGraph records the corpus source copies.  Reset to one fixed value
        # before capture; changed-value coverage is the eager gate above, while
        # the graph gate proves fixed-address replay stability through 28/58.
        apply_changed_input_schedule(0)
        for _ in range(args.warmup):
            cycle()
            synchronize()

        dist.barrier()
        graph = torch.xpu.XPUGraph()
        with torch.xpu.graph(graph):
            cycle()
        synchronize()

        exact_rows = []
        for replay in range(args.exact_replays):
            graph.replay()
            synchronize()
            reduced_mismatches, output_mismatches = mismatch_counts()
            exact_rows.append(
                {
                    "replay": replay,
                    "reduced_mismatches": reduced_mismatches,
                    "output_mismatches": output_mismatches,
                }
            )

        local_samples = []
        max_rank_samples = []
        for _ in range(args.timed_replays):
            synchronize()
            dist.barrier()
            started = time.perf_counter()
            graph.replay()
            synchronize()
            local_ms = (time.perf_counter() - started) * 1000.0
            local_samples.append(local_ms)
            local_time = torch.tensor(local_ms, dtype=torch.float64, device=device)
            rank_times = [torch.empty_like(local_time) for _ in range(world_size)]
            dist.all_gather(rank_times, local_time)
            max_rank_samples.append(max(float(value.item()) for value in rank_times))

        changed_eager_passed = not any(
            row["reduced_mismatches"] or any(row["output_mismatches"].values())
            for row in changed_eager_rows
        )
        graph_passed = not any(
            row["reduced_mismatches"] or any(row["output_mismatches"].values())
            for row in exact_rows
        )
        return {
            "kind": kind,
            "passed": (
                changed_eager_passed and collective_eager_passed and graph_passed
            ),
            "changed_eager_passed": changed_eager_passed,
            "changed_eager_epochs": changed_eager_rows,
            "collective_eager_passed": collective_eager_passed,
            "collective_eager_mismatches": collective_eager_mismatches,
            "collective_eager_row_mismatches": collective_eager_row_mismatches,
            "collective_eager_row_matches_local_count": (
                collective_eager_row_matches_local
            ),
            "collective_eager_duplicate_row_mismatches": (
                collective_eager_duplicate_row_mismatches
            ),
            "collective_eager_max_abs_diff": collective_eager_max_abs_diff,
            "graph_passed": graph_passed,
            "exact_replays": exact_rows,
            "local_wall_ms_samples": local_samples,
            "max_rank_wall_ms_samples": max_rank_samples,
            "max_rank_wall_ms_median": statistics.median(max_rank_samples),
        }

    path_results = [run_path(args.path)]
    extension_path = Path(xpu_extension.__file__).resolve()
    rank_result = {
        "rank": rank,
        "device": str(device),
        "device_name": torch.xpu.get_device_name(device),
        "width": args.width,
        "paths": path_results,
        "xpu_extension": str(extension_path),
        "xpu_extension_sha256": sha256(extension_path),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rank_output = args.output.with_suffix(args.output.suffix + f".rank{rank}.json")
    rank_output.write_text(json.dumps(rank_result, indent=2, sort_keys=True) + "\n")
    dist.barrier()

    passed = path_results[0]["passed"]
    if rank == 0:
        ranks = [
            json.loads(
                args.output.with_suffix(
                    args.output.suffix + f".rank{item}.json"
                ).read_text()
            )
            for item in range(world_size)
        ]
        result = {
            "classification": (
                "deepseek_v4_sequential_mwidth_corpus_path"
                if args.source_width == args.width
                else "deepseek_v4_row_tiled_real_m2_corpus_width_path"
            ),
            "passed": passed
            and all(
                row["paths"][0]["passed"]
                for row in ranks
            ),
            "scope": "TP4 allreduce plus MHC component geometry; not endpoint throughput or acceptance",
            "corpus": str(root),
            "world_size": world_size,
            "width": args.width,
            "source_width": args.source_width,
            "path": args.path,
            "diagnostic": args.diagnostic,
            "allreduces": ALLREDUCES,
            "mhc_boundaries": MHC_BOUNDARIES,
            "changed_eager_epochs": args.changed_eager_epochs,
            "warmup": args.warmup,
            "exact_replays": args.exact_replays,
            "timed_replays": args.timed_replays,
            "max_rank_wall_ms_median": path_results[0]["max_rank_wall_ms_median"],
            "ranks": ranks,
        }
        rendered = json.dumps(result, indent=2, sort_keys=True)
        print(rendered)
        args.output.write_text(rendered + "\n")

    dist.barrier()
    dist.destroy_process_group()
    return 0 if passed or args.diagnostic else 1


if __name__ == "__main__":
    raise SystemExit(main())
