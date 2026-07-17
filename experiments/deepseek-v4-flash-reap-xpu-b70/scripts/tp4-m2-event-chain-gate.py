#!/usr/bin/env python3
"""Gate the fixed-M2 oneCCL event-chain candidate against ordinary XCCL."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import time

import torch
import torch.distributed as dist
import vllm_xpu_kernels._C  # noqa: F401
import vllm_xpu_kernels._xpu_C as xpu_extension


ROWS = 2
HIDDEN = 4096
HC = 4
HC3 = 24
EPS = 1e-6


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def mapped_libraries(pattern: str) -> list[str]:
    rows = set()
    for line in Path("/proc/self/maps").read_text().splitlines():
        if pattern in line:
            rows.add(line.split()[-1])
    return sorted(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collectives", type=int, default=87)
    parser.add_argument("--mhc-boundaries", type=int, default=85)
    parser.add_argument("--warmup", type=int, default=8)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--graph-replays", type=int, default=0)
    parser.add_argument("--required-save-ms", type=float, default=0.50)
    parser.add_argument("--rank-skew-us", type=int, default=0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.collectives != args.mhc_boundaries + 2:
        raise ValueError("expected one leading and one trailing non-MHC reduction")
    if os.environ.get("B70_ONECCL_ENABLE_M2_EVENT_CHAIN") != "1":
        raise ValueError("B70_ONECCL_ENABLE_M2_EVENT_CHAIN=1 is required")

    rank = int(os.environ["RANK"])
    local_rank = int(os.environ["LOCAL_RANK"])
    world_size = int(os.environ["WORLD_SIZE"])
    if world_size != 4:
        raise ValueError(f"requires world_size=4, got {world_size}")

    torch.xpu.set_device(local_rank)
    device = torch.device(f"xpu:{local_rank}")
    dist.init_process_group(backend="xccl", device_id=device)
    stream = torch.xpu.current_stream(device)

    index = torch.arange(
        args.collectives * ROWS * HIDDEN, dtype=torch.int32, device=device
    ).reshape(args.collectives, ROWS, HIDDEN)
    base = index.remainder(13).to(torch.bfloat16)
    local_values = torch.empty_like(base)
    analytic_reduced = torch.empty_like(base)

    baseline_partial = [torch.empty_like(base[0]) for _ in range(args.collectives)]
    baseline_reduced = [torch.empty_like(base[0]) for _ in range(args.collectives)]
    candidate_partial = [torch.empty_like(base[0]) for _ in range(args.collectives)]
    candidate_reduced = [torch.empty_like(base[0]) for _ in range(args.collectives)]

    h = torch.arange(HIDDEN, dtype=torch.float32, device=device)
    k = torch.arange(HC * HIDDEN, dtype=torch.float32, device=device)
    residual_bank = torch.stack(
        [
            torch.stack(
                [
                    torch.stack(
                        [
                            torch.cos(
                                h * (0.00037 * (channel + 1))
                                + boundary * 0.0013
                                + row * 0.023
                            )
                            .mul_(channel + 0.75)
                            .to(torch.bfloat16)
                            for channel in range(HC)
                        ]
                    )
                    for row in range(ROWS)
                ]
            )
            for boundary in range(args.mhc_boundaries)
        ]
    )
    post_bank = (
        torch.arange(
            args.mhc_boundaries * ROWS * HC,
            dtype=torch.float32,
            device=device,
        )
        .reshape(args.mhc_boundaries, ROWS, HC, 1)
        .mul_(0.003)
        .sub_(0.4)
    )
    comb_bank = (
        torch.arange(
            args.mhc_boundaries * ROWS * HC * HC,
            dtype=torch.float32,
            device=device,
        )
        .reshape(args.mhc_boundaries, ROWS, HC, HC)
        .remainder_(37)
        .mul_(0.007)
        .sub_(0.11)
    )
    base_fn = torch.stack(
        [
            torch.sin(k * (0.000013 * (item + 1)) + item * 0.071)
            .mul_(0.00035)
            .add_(torch.cos(k * 0.000009 + item * 0.019) * 0.00015)
            for item in range(HC3)
        ]
    )
    fn_bank = torch.stack(
        [base_fn + boundary * 0.0000001 for boundary in range(args.mhc_boundaries)]
    )
    scale_bank = torch.stack(
        [
            torch.tensor([0.7, 0.8, 0.9], dtype=torch.float32, device=device).add_(
                boundary * 0.00001
            )
            for boundary in range(args.mhc_boundaries)
        ]
    )
    hc_base_bank = torch.stack(
        [
            torch.linspace(
                -0.12 + boundary * 0.00001,
                0.13 + boundary * 0.00001,
                HC3,
                dtype=torch.float32,
                device=device,
            )
            for boundary in range(args.mhc_boundaries)
        ]
    )

    def make_output_bank() -> tuple[torch.Tensor, ...]:
        return (
            torch.empty_like(residual_bank),
            torch.empty_like(post_bank),
            torch.empty_like(comb_bank),
            torch.empty(
                (args.mhc_boundaries, ROWS, HIDDEN),
                dtype=torch.bfloat16,
                device=device,
            ),
            torch.empty(
                (args.mhc_boundaries, 1), dtype=torch.bfloat16, device=device
            ),
        )

    baseline_outputs = make_output_bank()
    candidate_outputs = make_output_bank()
    reference_outputs = make_output_bank()

    def prepare(epoch: int) -> None:
        epoch_value = epoch % 7
        local_values.copy_(base + rank * 2 + epoch_value)
        analytic_reduced.copy_(base * world_size + 12 + epoch_value * world_size)

    def native_mhc(
        x: torch.Tensor,
        boundary: int,
        outputs: tuple[torch.Tensor, ...],
    ) -> None:
        residual_out, next_post, next_comb, layer_input, witnesses = outputs
        torch.ops._xpu_C.mhc_post_pre_m2_out(
            x,
            residual_bank[boundary],
            post_bank[boundary],
            comb_bank[boundary],
            fn_bank[boundary],
            scale_bank[boundary],
            hc_base_bank[boundary],
            residual_out[boundary],
            next_post[boundary],
            next_comb[boundary],
            layer_input[boundary],
            EPS,
            EPS,
            EPS,
            2.0,
            20,
        )
        witnesses[boundary].copy_(layer_input[boundary].reshape(-1)[:1])

    def baseline() -> None:
        for collective in range(args.collectives):
            baseline_partial[collective].copy_(local_values[collective])
            baseline_reduced[collective].copy_(baseline_partial[collective])
            dist.all_reduce(baseline_reduced[collective])
            if 1 <= collective <= args.mhc_boundaries:
                native_mhc(
                    baseline_reduced[collective],
                    collective - 1,
                    baseline_outputs,
                )

    def candidate() -> None:
        residual_out, next_post, next_comb, layer_input, witnesses = candidate_outputs
        for collective in range(args.collectives):
            candidate_partial[collective].copy_(local_values[collective])
            if not 1 <= collective <= args.mhc_boundaries:
                candidate_reduced[collective].copy_(candidate_partial[collective])
                dist.all_reduce(candidate_reduced[collective])
                continue
            boundary = collective - 1
            torch.ops._xpu_C.tp4_oneccl_allreduce_mhc_post_pre_m2_out(
                candidate_partial[collective],
                candidate_reduced[collective],
                residual_bank[boundary],
                post_bank[boundary],
                comb_bank[boundary],
                fn_bank[boundary],
                scale_bank[boundary],
                hc_base_bank[boundary],
                residual_out[boundary],
                next_post[boundary],
                next_comb[boundary],
                layer_input[boundary],
                EPS,
                EPS,
                EPS,
                2.0,
                20,
            )
            # Keep this separate: it makes every consumer completion visible to
            # eager execution and to a later graph-capture gate.
            witnesses[boundary].copy_(layer_input[boundary].reshape(-1)[:1])

    def reference() -> None:
        for boundary in range(args.mhc_boundaries):
            native_mhc(analytic_reduced[boundary + 1], boundary, reference_outputs)

    def synchronize() -> None:
        stream.synchronize()

    def max_rank_time_ms(call) -> tuple[float, float]:
        synchronize()
        dist.barrier()
        if args.rank_skew_us and rank:
            time.sleep(args.rank_skew_us * rank / 1_000_000.0)
        started = time.perf_counter()
        call()
        synchronize()
        local_ms = (time.perf_counter() - started) * 1000.0
        local_time = torch.tensor(local_ms, dtype=torch.float64, device=device)
        rank_times = [torch.empty_like(local_time) for _ in range(world_size)]
        dist.all_gather(rank_times, local_time)
        return local_ms, max(float(rank_time.item()) for rank_time in rank_times)

    # Warm the ordinary oneCCL path so the default-off bridge can register the
    # exact TP4/BF16/SUM/count=8192 communicator and stream identity.
    prepare(0)
    baseline_reduced[0].copy_(local_values[0])
    dist.all_reduce(baseline_reduced[0])
    synchronize()
    reference()
    synchronize()
    for epoch in range(args.warmup):
        prepare(epoch + 11)
        baseline()
        synchronize()
        prepare(epoch + 31)
        candidate()
        synchronize()

    names = ("baseline", "candidate")
    calls = {"baseline": baseline, "candidate": candidate}
    outputs = {"baseline": baseline_outputs, "candidate": candidate_outputs}
    reduced_banks = {
        "baseline": baseline_reduced,
        "candidate": candidate_reduced,
    }
    local_samples = {name: [] for name in names}
    max_rank_samples = {name: [] for name in names}
    reduced_mismatches = {name: [] for name in names}
    mhc_mismatches = {name: [] for name in names}

    for epoch in range(args.epochs):
        prepare(epoch + 101)
        synchronize()
        reference()
        synchronize()
        order = names if epoch % 2 == 0 else tuple(reversed(names))
        for name in order:
            local_ms, max_ms = max_rank_time_ms(calls[name])
            local_samples[name].append(local_ms)
            max_rank_samples[name].append(max_ms)
            reduced_mismatches[name].append(
                int((torch.stack(reduced_banks[name]) != analytic_reduced).sum().item())
            )
            mhc_mismatches[name].append(
                [
                    int((actual != expected).sum().item())
                    for actual, expected in zip(
                        outputs[name][:-1], reference_outputs[:-1], strict=True
                    )
                ]
            )

    graph_samples = {name: [] for name in names}
    graph_reduced_mismatches = {name: [] for name in names}
    graph_mhc_mismatches = {name: [] for name in names}
    if args.graph_replays:
        prepare(701)
        synchronize()
        dist.barrier()
        baseline_graph = torch.xpu.XPUGraph()
        with torch.xpu.graph(baseline_graph):
            baseline()
        synchronize()

        prepare(702)
        synchronize()
        dist.barrier()
        candidate_graph = torch.xpu.XPUGraph()
        with torch.xpu.graph(candidate_graph):
            candidate()
        synchronize()
        graphs = {"baseline": baseline_graph, "candidate": candidate_graph}

        for epoch in range(args.graph_replays):
            prepare(epoch + 801)
            synchronize()
            reference()
            synchronize()
            order = names if epoch % 2 == 0 else tuple(reversed(names))
            for name in order:
                _, max_ms = max_rank_time_ms(graphs[name].replay)
                graph_samples[name].append(max_ms)
                graph_reduced_mismatches[name].append(
                    int(
                        (torch.stack(reduced_banks[name]) != analytic_reduced)
                        .sum()
                        .item()
                    )
                )
                graph_mhc_mismatches[name].append(
                    [
                        int((actual != expected).sum().item())
                        for actual, expected in zip(
                            outputs[name][:-1], reference_outputs[:-1], strict=True
                        )
                    ]
                )

    medians = {
        name: statistics.median(samples)
        for name, samples in max_rank_samples.items()
    }
    saved_ms = medians["baseline"] - medians["candidate"]
    passed_correctness = not any(
        mismatch for rows in reduced_mismatches.values() for mismatch in rows
    ) and not any(
        mismatch
        for epochs in mhc_mismatches.values()
        for row in epochs
        for mismatch in row
    )
    graph_medians = {
        name: statistics.median(samples)
        for name, samples in graph_samples.items()
        if samples
    }
    graph_saved_ms = (
        graph_medians["baseline"] - graph_medians["candidate"]
        if graph_medians
        else None
    )
    passed_graph_correctness = not args.graph_replays or (
        not any(
            mismatch
            for rows in graph_reduced_mismatches.values()
            for mismatch in rows
        )
        and not any(
            mismatch
            for epochs in graph_mhc_mismatches.values()
            for row in epochs
            for mismatch in row
        )
    )
    passed_graph_performance = not args.graph_replays or (
        passed_graph_correctness
        and graph_saved_ms is not None
        and graph_saved_ms >= args.required_save_ms
    )
    extension_path = Path(xpu_extension.__file__).resolve()
    local_result = {
        "rank": rank,
        "device": str(device),
        "device_name": torch.xpu.get_device_name(device),
        "torch": torch.__version__,
        "xpu_extension": str(extension_path),
        "xpu_extension_sha256": sha256(extension_path),
        "libccl_maps": mapped_libraries("libccl.so"),
        "local_wall_ms_samples": local_samples,
        "graph_max_rank_wall_ms_samples": graph_samples,
        "reduced_mismatches_by_mode_and_epoch": reduced_mismatches,
        "mhc_output_mismatches_by_mode_and_epoch": mhc_mismatches,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rank_output = args.output.with_suffix(args.output.suffix + f".rank{rank}.json")
    rank_output.write_text(json.dumps(local_result, indent=2, sort_keys=True) + "\n")
    dist.barrier()

    if rank == 0:
        ranks = [
            json.loads(
                args.output.with_suffix(args.output.suffix + f".rank{item}.json").read_text()
            )
            for item in range(world_size)
        ]
        result = {
            "classification": "deepseek_v4_mtp1_m2_tp4_oneccl_event_chain_gate",
            "scope": "fixed M2 eager component A/B; not a model throughput result",
            "passed_correctness": passed_correctness,
            "passed_performance_gate": passed_correctness
            and saved_ms >= args.required_save_ms,
            "passed_graph_correctness": passed_graph_correctness,
            "passed_graph_performance_gate": passed_graph_performance,
            "world_size": world_size,
            "rows_per_collective": ROWS,
            "collectives": args.collectives,
            "mhc_boundaries": args.mhc_boundaries,
            "warmup": args.warmup,
            "epochs": args.epochs,
            "graph_replays": args.graph_replays,
            "rank_skew_us": args.rank_skew_us,
            "max_rank_wall_ms_samples": max_rank_samples,
            "max_rank_wall_ms_medians": medians,
            "saved_ms": saved_ms,
            "graph_max_rank_wall_ms_samples": graph_samples,
            "graph_max_rank_wall_ms_medians": graph_medians,
            "graph_saved_ms": graph_saved_ms,
            "required_save_ms": args.required_save_ms,
            "correctness": {
                "reduced_mismatches_by_mode_and_epoch": reduced_mismatches,
                "mhc_output_mismatches_by_mode_and_epoch": mhc_mismatches,
                "graph_reduced_mismatches_by_mode_and_epoch": (
                    graph_reduced_mismatches
                ),
                "graph_mhc_output_mismatches_by_mode_and_epoch": (
                    graph_mhc_mismatches
                ),
            },
            "ranks": ranks,
        }
        rendered = json.dumps(result, indent=2, sort_keys=True)
        print(rendered)
        args.output.write_text(rendered + "\n")

    dist.barrier()
    dist.destroy_process_group()
    passed = (
        passed_correctness
        and saved_ms >= args.required_save_ms
        and passed_graph_correctness
        and passed_graph_performance
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
