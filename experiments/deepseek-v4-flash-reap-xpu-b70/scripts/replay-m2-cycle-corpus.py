#!/usr/bin/env python3
"""Replay the real DeepSeek V4 M=2 TP4/MHC cycle without loading the model."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import time
from typing import Any

import torch
import torch.distributed as dist
import vllm_xpu_kernels._C  # noqa: F401
import vllm_xpu_kernels._xpu_C as xpu_extension


ALLREDUCES = 87
MHC_BOUNDARIES = 85


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus", type=Path)
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
    allreduce_rows = load_rows(root, rank, "allreduce_m2", ALLREDUCES)
    mhc_rows = load_rows(root, rank, "mhc_post_pre_m2", MHC_BOUNDARIES)
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

    local_partial = [
        get_tensor(row["tensors"]["local_partial"]) for row in allreduce_rows
    ]
    expected_reduced = [
        get_tensor(row["tensors"]["reduced"]) for row in allreduce_rows
    ]
    reduced = [torch.empty_like(tensor) for tensor in expected_reduced]

    def mhc_input(name: str) -> list[torch.Tensor]:
        return [get_tensor(row["tensors"][name]) for row in mhc_rows]

    residual = mhc_input("residual")
    post_mix = mhc_input("post_mix")
    comb_res_mix = mhc_input("comb_res_mix")
    fn = mhc_input("fn")
    hc_scale = mhc_input("hc_scale")
    hc_base = mhc_input("hc_base")
    expected_outputs = {
        name: mhc_input(name)
        for name in (
            "residual_out",
            "next_post_mix",
            "next_comb_mix",
            "layer_input",
        )
    }
    outputs = {
        name: [torch.empty_like(tensor) for tensor in tensors]
        for name, tensors in expected_outputs.items()
    }
    witnesses = [torch.empty(1, dtype=torch.bfloat16, device=device) for _ in mhc_rows]

    def cycle() -> None:
        for collective in range(ALLREDUCES):
            reduced[collective].copy_(local_partial[collective])
            dist.all_reduce(reduced[collective])
            if not 1 <= collective <= MHC_BOUNDARIES:
                continue
            boundary = collective - 1
            torch.ops._xpu_C.mhc_post_pre_m2_out(
                reduced[collective],
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
            witnesses[boundary].copy_(
                outputs["layer_input"][boundary].reshape(-1)[:1]
            )

    def synchronize() -> None:
        torch.xpu.synchronize(device)

    def mismatch_counts() -> tuple[int, dict[str, int]]:
        reduced_mismatch = sum(
            int((actual != expected).sum().item())
            for actual, expected in zip(reduced, expected_reduced, strict=True)
        )
        output_mismatches = {
            name: sum(
                int((actual != expected).sum().item())
                for actual, expected in zip(
                    outputs[name], expected_outputs[name], strict=True
                )
            )
            for name in outputs
        }
        return reduced_mismatch, output_mismatches

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
        reduced_mismatch, output_mismatches = mismatch_counts()
        exact_rows.append(
            {
                "replay": replay,
                "reduced_mismatches": reduced_mismatch,
                "output_mismatches": output_mismatches,
            }
        )

    max_rank_samples = []
    local_samples = []
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

    passed = not any(
        row["reduced_mismatches"]
        or any(row["output_mismatches"].values())
        for row in exact_rows
    )
    extension_path = Path(xpu_extension.__file__).resolve()
    rank_result = {
        "rank": rank,
        "device": str(device),
        "device_name": torch.xpu.get_device_name(device),
        "passed": passed,
        "exact_replays": exact_rows,
        "local_wall_ms_samples": local_samples,
        "xpu_extension": str(extension_path),
        "xpu_extension_sha256": sha256(extension_path),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rank_output = args.output.with_suffix(args.output.suffix + f".rank{rank}.json")
    rank_output.write_text(json.dumps(rank_result, indent=2, sort_keys=True) + "\n")
    dist.barrier()

    if rank == 0:
        ranks = [
            json.loads(
                args.output.with_suffix(args.output.suffix + f".rank{item}.json").read_text()
            )
            for item in range(world_size)
        ]
        result = {
            "classification": "deepseek_v4_mtp1_m2_real_cycle_fixed_buffer_replay",
            "passed": passed and all(row["passed"] for row in ranks),
            "corpus": str(root),
            "world_size": world_size,
            "allreduces": ALLREDUCES,
            "mhc_boundaries": MHC_BOUNDARIES,
            "warmup": args.warmup,
            "exact_replays": args.exact_replays,
            "timed_replays": args.timed_replays,
            "max_rank_wall_ms_samples": max_rank_samples,
            "max_rank_wall_ms_median": statistics.median(max_rank_samples),
            "ranks": ranks,
        }
        rendered = json.dumps(result, indent=2, sort_keys=True)
        print(rendered)
        args.output.write_text(rendered + "\n")

    dist.barrier()
    dist.destroy_process_group()
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
