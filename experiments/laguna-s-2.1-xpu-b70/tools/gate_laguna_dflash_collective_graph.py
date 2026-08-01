#!/usr/bin/env python3
"""Changing-input TP4 oracle for Laguna's 13 DFlash all-reduce boundaries."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import time
from typing import Any

import torch
import torch.distributed as dist


def _source_value(
    base: torch.Tensor, *, rank: int, iteration: int
) -> torch.Tensor:
    # Small integral BF16 values keep the complete oracle exactly representable.
    return base + rank * 3 + (iteration % 17)


def _expected(
    base: torch.Tensor,
    *,
    world_size: int,
    iteration: int,
    stage: int,
) -> torch.Tensor:
    rank_offset_sum = 3 * world_size * (world_size - 1) // 2
    reduced = (
        base * world_size
        + rank_offset_sum
        + world_size * ((iteration % 17) + stage)
    )
    return reduced + (stage % 7)


def _loaded_ccl_paths() -> list[str]:
    return sorted(
        {
            line.rsplit(maxsplit=1)[-1]
            for line in Path("/proc/self/maps").read_text().splitlines()
            if "libccl.so" in line
            and line.rsplit(maxsplit=1)[-1].startswith("/")
        }
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("direct", "graph"), required=True)
    parser.add_argument("--rows", type=int, default=12)
    parser.add_argument("--hidden-size", type=int, default=3072)
    parser.add_argument("--stages", type=int, default=13)
    parser.add_argument("--warmup", type=int, default=8)
    parser.add_argument("--iterations", type=int, default=512)
    parser.add_argument("--timing-warmup", type=int, default=20)
    parser.add_argument("--timing-samples", type=int, default=9)
    parser.add_argument("--timing-transactions", type=int, default=200)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-libccl", type=Path)
    parser.add_argument("--expected-libccl-sha256")
    args = parser.parse_args()

    if args.rows <= 0 or args.hidden_size <= 0 or args.stages <= 0:
        raise ValueError("rows, hidden size, and stages must be positive")
    if args.timing_samples <= 0 or args.timing_transactions <= 0:
        raise ValueError("timing sample counts must be positive")

    local_rank = int(os.environ["LOCAL_RANK"])
    rank = int(os.environ["RANK"])
    world_size = int(os.environ["WORLD_SIZE"])
    if world_size != 4:
        raise ValueError(f"Laguna probe requires world_size=4, got {world_size}")

    torch.xpu.set_device(local_rank)
    dist.init_process_group(backend="xccl")
    device = torch.device(f"xpu:{local_rank}")
    numel = args.rows * args.hidden_size
    base = (
        torch.arange(numel, dtype=torch.int32, device=device)
        .remainder_(31)
        .to(torch.bfloat16)
        .reshape(args.rows, args.hidden_size)
    )
    sources = [torch.empty_like(base) for _ in range(args.stages)]
    reduced = [torch.empty_like(base) for _ in range(args.stages)]
    outputs = [torch.empty_like(base) for _ in range(args.stages)]

    def publish(iteration: int) -> None:
        value = _source_value(base, rank=rank, iteration=iteration)
        for source in sources:
            source.copy_(value)

    def transaction() -> None:
        for stage in range(args.stages):
            torch.add(sources[stage], stage, out=reduced[stage])
            work = dist.all_reduce(reduced[stage], async_op=True)
            work.wait()
            torch.add(reduced[stage], stage % 7, out=outputs[stage])

    for iteration in range(args.warmup):
        publish(iteration)
        transaction()
    torch.xpu.synchronize()
    dist.barrier()

    graph: torch.xpu.XPUGraph | None = None
    if args.mode == "graph":
        graph = torch.xpu.XPUGraph()
        publish(0)
        torch.xpu.synchronize()
        dist.barrier()
        with torch.xpu.graph(graph):
            transaction()
        torch.xpu.synchronize()
        dist.barrier()

    first_mismatch: dict[str, Any] | None = None
    mismatch_iterations = 0
    for iteration in range(args.iterations):
        publish(iteration)
        torch.xpu.synchronize()
        if graph is None:
            transaction()
        else:
            graph.replay()
        torch.xpu.synchronize()

        for stage, output in enumerate(outputs):
            expected = _expected(
                base,
                world_size=world_size,
                iteration=iteration,
                stage=stage,
            )
            if torch.equal(output, expected):
                continue
            mismatch_iterations += 1
            if first_mismatch is None:
                diff = (output.float() - expected.float()).abs().reshape(-1)
                indices = diff.nonzero().reshape(-1)
                first_index = int(indices[0].item())
                first_mismatch = {
                    "iteration": iteration,
                    "stage": stage,
                    "flat_index": first_index,
                    "actual": float(output.reshape(-1)[first_index].item()),
                    "expected": float(expected.reshape(-1)[first_index].item()),
                    "max_abs_diff": float(diff.max().item()),
                    "mismatch_elements": int(indices.numel()),
                }
            break

    timing_iteration = 3
    publish(timing_iteration)
    torch.xpu.synchronize()
    dist.barrier()
    for _ in range(args.timing_warmup):
        if graph is None:
            transaction()
        else:
            graph.replay()
    torch.xpu.synchronize()

    timing_ms: list[float] = []
    for _ in range(args.timing_samples):
        start = time.perf_counter()
        for _ in range(args.timing_transactions):
            if graph is None:
                transaction()
            else:
                graph.replay()
        torch.xpu.synchronize()
        timing_ms.append(
            (time.perf_counter() - start) * 1000.0 / args.timing_transactions
        )

    for stage, output in enumerate(outputs):
        expected = _expected(
            base,
            world_size=world_size,
            iteration=timing_iteration,
            stage=stage,
        )
        if not torch.equal(output, expected):
            mismatch_iterations += 1
            if first_mismatch is None:
                first_mismatch = {
                    "iteration": "post_timing",
                    "stage": stage,
                }
            break

    loaded_paths = _loaded_ccl_paths()
    expected_path = (
        str(args.expected_libccl.resolve()) if args.expected_libccl else None
    )
    expected_loaded = expected_path is None or expected_path in loaded_paths
    expected_sha_ok = True
    actual_expected_sha: str | None = None
    if args.expected_libccl is not None and args.expected_libccl_sha256:
        actual_expected_sha = _sha256(args.expected_libccl)
        expected_sha_ok = actual_expected_sha == args.expected_libccl_sha256

    local_result = {
        "rank": rank,
        "local_rank": local_rank,
        "device": str(device),
        "shape": [args.rows, args.hidden_size],
        "dtype": "bfloat16",
        "stages": args.stages,
        "iterations": args.iterations,
        "mode": args.mode,
        "loaded_ccl_paths": loaded_paths,
        "expected_ccl_path": expected_path,
        "expected_ccl_loaded": expected_loaded,
        "expected_ccl_sha256": args.expected_libccl_sha256,
        "actual_expected_ccl_sha256": actual_expected_sha,
        "expected_ccl_sha256_ok": expected_sha_ok,
        "mismatch_iterations": mismatch_iterations,
        "first_mismatch": first_mismatch,
        "timing": {
            "warmup_transactions": args.timing_warmup,
            "samples": args.timing_samples,
            "transactions_per_sample": args.timing_transactions,
            "transaction_ms_samples": timing_ms,
            "transaction_ms_median": statistics.median(timing_ms),
        },
    }

    all_results: list[dict[str, Any] | None] = [None] * world_size
    dist.all_gather_object(all_results, local_result)
    local_passed = (
        mismatch_iterations == 0 and expected_loaded and expected_sha_ok
    )
    passed_flags: list[bool | None] = [None] * world_size
    dist.all_gather_object(passed_flags, local_passed)

    if rank == 0:
        passed = all(flag is True for flag in passed_flags)
        document = {
            "passed": passed,
            "backend": "xccl",
            "world_size": world_size,
            "mode": args.mode,
            "ranks": all_results,
            "fleet_max_rank_median_transaction_ms": max(
                result["timing"]["transaction_ms_median"]
                for result in all_results
                if result is not None
            ),
        }
        rendered = json.dumps(document, indent=2, sort_keys=True)
        print(rendered)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n")

    dist.destroy_process_group()
    return 0 if local_passed else 1


if __name__ == "__main__":
    sys.exit(main())
