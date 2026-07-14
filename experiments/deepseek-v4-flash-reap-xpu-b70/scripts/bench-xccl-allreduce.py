#!/usr/bin/env python3
"""Measure ordered XCCL all-reduce latency at DeepSeek decode shapes."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time

import torch
import torch.distributed as dist


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=1)
    parser.add_argument("--hidden-size", type=int, default=4096)
    parser.add_argument("--warmups", type=int, default=100)
    parser.add_argument("--iterations", type=int, default=500)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    local_rank = int(os.environ["LOCAL_RANK"])
    rank = int(os.environ["RANK"])
    torch.xpu.set_device(local_rank)
    dist.init_process_group("xccl")

    value = torch.full(
        (args.rows, args.hidden_size),
        float(rank + 1),
        dtype=torch.bfloat16,
        device=f"xpu:{local_rank}",
    )
    expected = float(sum(range(1, dist.get_world_size() + 1)))

    for _ in range(args.warmups):
        value.fill_(float(rank + 1))
        dist.all_reduce(value)
    torch.xpu.synchronize()
    dist.barrier(device_ids=[local_rank])

    samples_us: list[float] = []
    for _ in range(args.iterations):
        value.fill_(float(rank + 1))
        start = time.perf_counter_ns()
        dist.all_reduce(value)
        torch.xpu.synchronize()
        samples_us.append((time.perf_counter_ns() - start) / 1_000.0)

    valid = float(value[0, 0].cpu()) == expected
    gathered: list[dict[str, float | int | bool] | None] = [
        None for _ in range(dist.get_world_size())
    ]
    local = {
        "rank": rank,
        "valid": valid,
        "mean_us": statistics.fmean(samples_us),
        "median_us": statistics.median(samples_us),
        "p95_us": sorted(samples_us)[int(len(samples_us) * 0.95) - 1],
        "min_us": min(samples_us),
        "max_us": max(samples_us),
    }
    dist.all_gather_object(gathered, local)
    if rank == 0:
        print(
            json.dumps(
                {
                    "world_size": dist.get_world_size(),
                    "dtype": "bfloat16",
                    "shape": [args.rows, args.hidden_size],
                    "bytes_per_rank": value.numel() * value.element_size(),
                    "warmups": args.warmups,
                    "iterations": args.iterations,
                    "ranks": gathered,
                    "decoder_step_87x_rank0_median_ms": (
                        float(gathered[0]["median_us"]) * 87 / 1_000.0
                    ),
                },
                sort_keys=True,
            ),
            flush=True,
        )
    dist.destroy_process_group()


if __name__ == "__main__":
    main()
