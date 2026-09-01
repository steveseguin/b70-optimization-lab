#!/usr/bin/env python3
"""Probe whether TP4 XCCL all-reduce is exact under XPU graph replay.

This is deliberately the production Flash-Next target-decode collective shape:
one BF16 row of width 2560 (5,120 bytes).  It records only the collective in
the graph.  Per-replay inputs are changed outside the graph so a stale/no-op
replay cannot pass the oracle.
"""

import argparse
import hashlib
import json
import os
import time

import torch
import torch.distributed as dist


def digest(tensor: torch.Tensor) -> str:
    raw = tensor.contiguous().view(torch.uint8).cpu().numpy().tobytes()
    return hashlib.sha256(raw).hexdigest()


def input_for(rank: int, iteration: int, hidden: int) -> torch.Tensor:
    cols = torch.arange(hidden, dtype=torch.int64)
    # Exact BF16 integers, with both rank and replay iteration affecting every
    # row.  The sum stays well inside BF16's exact integer range.
    values = ((cols * 13 + rank * 29 + iteration * 7) % 127) - 63
    return values.to(torch.bfloat16).reshape(1, hidden)


def expected_for(iteration: int, hidden: int, world_size: int) -> torch.Tensor:
    return torch.stack(
        [input_for(rank, iteration, hidden) for rank in range(world_size)]
    ).sum(dim=0)


def timed_eager(
    tensor: torch.Tensor,
    rank: int,
    hidden: int,
    world_size: int,
    repeats: int,
) -> tuple[float, list[str]]:
    hashes: list[str] = []
    dist.barrier(device_ids=[rank])
    torch.xpu.synchronize()
    started = time.perf_counter_ns()
    for iteration in range(repeats):
        tensor.copy_(input_for(rank, iteration, hidden))
        dist.all_reduce(tensor, op=dist.ReduceOp.SUM)
        torch.xpu.synchronize()
        expected = expected_for(iteration, hidden, world_size)
        actual = tensor.cpu()
        if not torch.equal(actual, expected):
            raise AssertionError(f"eager mismatch at iteration {iteration}")
        hashes.append(digest(actual))
    elapsed_us = (time.perf_counter_ns() - started) / 1000
    return elapsed_us / repeats, hashes


def timed_graph(
    tensor: torch.Tensor,
    rank: int,
    hidden: int,
    world_size: int,
    repeats: int,
) -> tuple[float, list[str]]:
    graph = torch.xpu.XPUGraph()
    tensor.copy_(input_for(rank, 10_000, hidden))
    dist.barrier(device_ids=[rank])
    torch.xpu.synchronize()
    with torch.xpu.graph(graph):
        dist.all_reduce(tensor, op=dist.ReduceOp.SUM)
    torch.xpu.synchronize()

    hashes: list[str] = []
    dist.barrier(device_ids=[rank])
    torch.xpu.synchronize()
    started = time.perf_counter_ns()
    for iteration in range(repeats):
        tensor.copy_(input_for(rank, iteration, hidden))
        graph.replay()
        torch.xpu.synchronize()
        expected = expected_for(iteration, hidden, world_size)
        actual = tensor.cpu()
        if not torch.equal(actual, expected):
            raise AssertionError(f"graph mismatch at iteration {iteration}")
        hashes.append(digest(actual))
    elapsed_us = (time.perf_counter_ns() - started) / 1000
    return elapsed_us / repeats, hashes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hidden", type=int, default=2560)
    parser.add_argument("--repeats", type=int, default=100)
    args = parser.parse_args()
    if args.hidden <= 0:
        raise ValueError("hidden must be positive")
    if not 2 <= args.repeats <= 1000:
        raise ValueError("repeats must be in [2, 1000]")

    rank = int(os.environ["RANK"])
    local_rank = int(os.environ["LOCAL_RANK"])
    world_size = int(os.environ["WORLD_SIZE"])
    if world_size != 4 or rank != local_rank:
        raise RuntimeError("probe requires one local TP4 process per XPU")

    device = torch.device(f"xpu:{local_rank}")
    torch.xpu.set_device(device)
    dist.init_process_group("xccl")
    try:
        tensor = torch.empty((1, args.hidden), dtype=torch.bfloat16, device=device)
        eager_us, eager_hashes = timed_eager(
            tensor, rank, args.hidden, world_size, args.repeats
        )
        graph_us, graph_hashes = timed_graph(
            tensor, rank, args.hidden, world_size, args.repeats
        )
        if eager_hashes != graph_hashes:
            raise AssertionError("eager and graph replay hash series differ")

        print(
            json.dumps(
                {
                    "classification": "xpu_graph_xccl_exact_component_probe",
                    "dtype": "bfloat16",
                    "eager_mean_us": eager_us,
                    "graph_mean_us": graph_us,
                    "hidden": args.hidden,
                    "rank": rank,
                    "repeats": args.repeats,
                    "speedup": eager_us / graph_us,
                    "unique_hashes": len(set(graph_hashes)),
                    "world_size": world_size,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        dist.barrier(device_ids=[local_rank])
    finally:
        dist.destroy_process_group()


if __name__ == "__main__":
    main()
