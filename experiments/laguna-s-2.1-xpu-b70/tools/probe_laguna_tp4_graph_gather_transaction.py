#!/usr/bin/env python3
"""Changing-input TP4 oracle for Laguna's captured gather transaction."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

import torch
import torch.distributed as dist


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def input_for_iteration(
    base: torch.Tensor, *, rank: int, iteration: int
) -> torch.Tensor:
    return base + rank * 37 + (iteration % 19)


def expected_for_iteration(
    base: torch.Tensor, *, world_size: int, iteration: int
) -> tuple[torch.Tensor, torch.Tensor]:
    gathered = torch.cat(
        [
            input_for_iteration(base, rank=rank, iteration=iteration)
            for rank in range(world_size)
        ],
        dim=0,
    )
    reduced = gathered[0:1]
    for rank in range(1, world_size):
        reduced = reduced + gathered[rank : rank + 1]
    return gathered, reduced


def first_mismatch(
    actual: torch.Tensor, expected: torch.Tensor, iteration: int
) -> dict[str, Any] | None:
    if torch.equal(actual, expected):
        return None
    difference = (actual.float() - expected.float()).abs()
    indexes = difference.reshape(-1).nonzero().reshape(-1)
    index = int(indexes[0].item())
    return {
        "iteration": iteration,
        "flat_index": index,
        "actual": float(actual.reshape(-1)[index].item()),
        "expected": float(expected.reshape(-1)[index].item()),
        "mismatch_elements": int(indexes.numel()),
        "max_abs_diff": float(difference.max().item()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=512)
    parser.add_argument("--rows", type=int, default=12)
    parser.add_argument("--hidden-size", type=int, default=3072)
    parser.add_argument("--expected-libccl-sha256", required=True)
    parser.add_argument("--require-exclusive-libccl", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rank = int(os.environ["RANK"])
    local_rank = int(os.environ["LOCAL_RANK"])
    world_size = int(os.environ["WORLD_SIZE"])
    if world_size != 4:
        raise ValueError(f"Laguna transaction probe requires TP4, got {world_size}")
    if args.rows != 12 or args.hidden_size != 3072:
        raise ValueError("Laguna transaction probe requires [1,12,3072]")

    torch.xpu.set_device(local_rank)
    dist.init_process_group(backend="xccl")
    device = torch.device(f"xpu:{local_rank}")
    base = (
        torch.arange(args.rows * args.hidden_size, dtype=torch.int32, device=device)
        .remainder_(31)
        .to(torch.bfloat16)
        .reshape(1, args.rows, args.hidden_size)
    )
    source = torch.empty_like(base)
    fixed_input = torch.empty_like(base)
    gathered = torch.empty(
        (world_size, args.rows, args.hidden_size),
        dtype=torch.bfloat16,
        device=device,
    )
    consumer = torch.empty_like(base)

    for iteration in range(8):
        source.copy_(input_for_iteration(base, rank=rank, iteration=iteration))
        fixed_input.copy_(source)
        dist.all_gather_into_tensor(gathered, fixed_input)
        reduced = gathered[0:1]
        for source_rank in range(1, world_size):
            reduced = reduced + gathered[source_rank : source_rank + 1]
        consumer.copy_(reduced)
    torch.xpu.synchronize()
    dist.barrier()

    graph = torch.xpu.XPUGraph()
    source.copy_(input_for_iteration(base, rank=rank, iteration=0))
    torch.xpu.synchronize()
    dist.barrier()
    with torch.xpu.graph(graph):
        fixed_input.copy_(source)
        dist.all_gather_into_tensor(gathered, fixed_input)
        reduced = gathered[0:1]
        for source_rank in range(1, world_size):
            reduced = reduced + gathered[source_rank : source_rank + 1]
        consumer.copy_(reduced)
    torch.xpu.synchronize()
    dist.barrier()

    gather_mismatch_iterations = 0
    consumer_mismatch_iterations = 0
    first_gather_mismatch = None
    first_consumer_mismatch = None
    completed_iterations = 0
    for iteration in range(args.iterations):
        source.copy_(input_for_iteration(base, rank=rank, iteration=iteration))
        torch.xpu.synchronize()
        graph.replay()
        torch.xpu.synchronize()
        completed_iterations += 1

        expected_gathered, expected_consumer = expected_for_iteration(
            base, world_size=world_size, iteration=iteration
        )
        gather_mismatch = first_mismatch(gathered, expected_gathered, iteration)
        consumer_mismatch = first_mismatch(consumer, expected_consumer, iteration)
        if gather_mismatch is not None:
            gather_mismatch_iterations += 1
            if first_gather_mismatch is None:
                first_gather_mismatch = gather_mismatch
        if consumer_mismatch is not None:
            consumer_mismatch_iterations += 1
            if first_consumer_mismatch is None:
                first_consumer_mismatch = consumer_mismatch

    loaded_ccl_paths = sorted(
        {
            Path(line.rsplit(maxsplit=1)[-1])
            for line in Path("/proc/self/maps").read_text().splitlines()
            if "libccl.so" in line
            and line.rsplit(maxsplit=1)[-1].startswith("/")
        }
    )
    loaded_ccl = [
        {"path": str(path), "sha256": sha256_file(path)}
        for path in loaded_ccl_paths
    ]
    matching_ccl = [
        library
        for library in loaded_ccl
        if library["sha256"] == args.expected_libccl_sha256
    ]
    library_identity_passed = (
        len(matching_ccl) == 1
        and (not args.require_exclusive_libccl or len(loaded_ccl) == 1)
    )
    local_result = {
        "rank": rank,
        "local_rank": local_rank,
        "device": str(device),
        "shape": [1, args.rows, args.hidden_size],
        "dtype": "bfloat16",
        "requested_iterations": args.iterations,
        "completed_iterations": completed_iterations,
        "loaded_ccl": loaded_ccl,
        "expected_libccl_sha256": args.expected_libccl_sha256,
        "require_exclusive_libccl": args.require_exclusive_libccl,
        "library_identity_passed": library_identity_passed,
        "gather_mismatch_iterations": gather_mismatch_iterations,
        "consumer_mismatch_iterations": consumer_mismatch_iterations,
        "first_gather_mismatch": first_gather_mismatch,
        "first_consumer_mismatch": first_consumer_mismatch,
    }
    all_results: list[dict[str, Any] | None] = [None] * world_size
    dist.all_gather_object(all_results, local_result)

    local_passed = (
        library_identity_passed
        and gather_mismatch_iterations == 0
        and consumer_mismatch_iterations == 0
        and completed_iterations == args.iterations
    )
    pass_tensor = torch.tensor(int(local_passed), dtype=torch.int32, device=device)
    dist.all_reduce(pass_tensor, op=dist.ReduceOp.MIN)
    passed = bool(pass_tensor.item())
    if rank == 0:
        result = {
            "schema": "laguna-tp4-graph-gather-transaction-v1",
            "status": "PASS" if passed else "FAIL",
            "passed": passed,
            "backend": "xccl",
            "world_size": world_size,
            "queue_test": "torch.xpu.XPUGraph",
            "transaction": "producer-copy_all-gather_rank-ordered-bf16-consumer",
            "ranks": all_results,
        }
        rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
        print(rendered, end="")
    dist.destroy_process_group()
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
