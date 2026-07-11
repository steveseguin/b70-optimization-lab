#!/usr/bin/env python3
"""Exact TP2 XPU-graph replay probe for oneCCL's recorded LL256 all-reduce.

The Qwen27 TP2 target graph reduces BF16 tensors shaped ``[4, 5120]``.  This
probe captures only that collective, changes every input before every replay,
and compares every output element with an exactly representable BF16 oracle.
It is intentionally independent of vLLM so a oneCCL candidate can be rejected
before an expensive model endpoint run.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

import torch
import torch.distributed as dist


def _input_for_iteration(
    base: torch.Tensor,
    *,
    rank: int,
    iteration: int,
) -> torch.Tensor:
    # Keep values small integral BF16 numbers so reduction has an exact oracle.
    return base + rank * 3 + (iteration % 17)


def _expected_for_iteration(
    base: torch.Tensor,
    *,
    world_size: int,
    iteration: int,
) -> torch.Tensor:
    rank_offset_sum = 3 * world_size * (world_size - 1) // 2
    return base * world_size + rank_offset_sum + world_size * (iteration % 17)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("direct", "graph"), default="graph")
    parser.add_argument("--rows", type=int, default=4)
    parser.add_argument("--hidden-size", type=int, default=5120)
    parser.add_argument("--warmup", type=int, default=8)
    parser.add_argument("--iterations", type=int, default=512)
    parser.add_argument(
        "--timing-iterations",
        type=int,
        default=0,
        help=(
            "After exact validation, batch this many graph replays behind one "
            "host synchronization and report comparative replay latency."
        ),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    local_rank = int(os.environ["LOCAL_RANK"])
    rank = int(os.environ["RANK"])
    world_size = int(os.environ["WORLD_SIZE"])
    if world_size != 2:
        raise ValueError(f"this probe requires world_size=2, got {world_size}")

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
    static_input = torch.empty_like(base)

    for iteration in range(args.warmup):
        static_input.copy_(
            _input_for_iteration(base, rank=rank, iteration=iteration)
        )
        dist.all_reduce(static_input)
    torch.xpu.synchronize()
    dist.barrier()

    graph: torch.xpu.XPUGraph | None = None
    if args.mode == "graph":
        graph = torch.xpu.XPUGraph()
        static_input.copy_(_input_for_iteration(base, rank=rank, iteration=0))
        torch.xpu.synchronize()
        dist.barrier()
        with torch.xpu.graph(graph):
            work = dist.all_reduce(static_input, async_op=True)
            work.wait()
        torch.xpu.synchronize()
        dist.barrier()

    first_mismatch: dict[str, Any] | None = None
    mismatch_iterations = 0
    max_abs_diff = 0.0
    start = time.perf_counter()
    for iteration in range(args.iterations):
        static_input.copy_(
            _input_for_iteration(base, rank=rank, iteration=iteration)
        )
        # Match vLLM's fixed-address replay while making input publication
        # explicit, so this probe isolates the collective graph itself.
        torch.xpu.synchronize()
        if graph is None:
            dist.all_reduce(static_input)
        else:
            graph.replay()
        torch.xpu.synchronize()

        expected = _expected_for_iteration(
            base, world_size=world_size, iteration=iteration
        )
        equal = torch.equal(static_input, expected)
        if not equal:
            mismatch_iterations += 1
            diff = (static_input.float() - expected.float()).abs()
            iteration_max = float(diff.max().item())
            max_abs_diff = max(max_abs_diff, iteration_max)
            if first_mismatch is None:
                mismatch_flat = diff.reshape(-1).nonzero().reshape(-1)
                first_index = int(mismatch_flat[0].item())
                first_mismatch = {
                    "iteration": iteration,
                    "flat_index": first_index,
                    "actual": float(static_input.reshape(-1)[first_index].item()),
                    "expected": float(expected.reshape(-1)[first_index].item()),
                    "max_abs_diff": iteration_max,
                    "mismatch_elements": int(mismatch_flat.numel()),
                }

    torch.xpu.synchronize()
    elapsed_s = time.perf_counter() - start
    loaded_ccl_paths = sorted(
        {
            line.rsplit(maxsplit=1)[-1]
            for line in Path("/proc/self/maps").read_text().splitlines()
            if "libccl.so" in line and line.rsplit(maxsplit=1)[-1].startswith("/")
        }
    )
    local_result = {
        "rank": rank,
        "local_rank": local_rank,
        "device": str(device),
        "rows": args.rows,
        "hidden_size": args.hidden_size,
        "dtype": "bfloat16",
        "iterations": args.iterations,
        "mode": args.mode,
        "loaded_ccl_paths": loaded_ccl_paths,
        "mismatch_iterations": mismatch_iterations,
        "first_mismatch": first_mismatch,
        "max_abs_diff": max_abs_diff,
        "avg_replay_ms_including_sync_and_validation": elapsed_s
        * 1000.0
        / args.iterations,
    }

    if args.timing_iterations:
        if graph is None:
            raise ValueError("--timing-iterations requires --mode graph")
        timing_input = _input_for_iteration(base, rank=rank, iteration=3)
        # Include the fixed-address input publication that precedes collective
        # replay, but amortize host/device synchronization and validation. This
        # is a comparative screen, not an endpoint throughput claim.
        torch.xpu.synchronize()
        dist.barrier()
        timing_start = time.perf_counter()
        for _ in range(args.timing_iterations):
            static_input.copy_(timing_input)
            graph.replay()
        torch.xpu.synchronize()
        timing_elapsed_s = time.perf_counter() - timing_start
        timing_expected = _expected_for_iteration(
            base, world_size=world_size, iteration=3
        )
        timing_passed = torch.equal(static_input, timing_expected)
        local_result["batched_graph_timing"] = {
            "iterations": args.timing_iterations,
            "total_ms": timing_elapsed_s * 1000.0,
            "ms_per_copy_and_replay": timing_elapsed_s
            * 1000.0
            / args.timing_iterations,
            "final_output_passed": timing_passed,
        }
        if not timing_passed:
            mismatch_iterations += 1
            local_result["mismatch_iterations"] = mismatch_iterations
    all_results: list[dict[str, Any] | None] = [None] * world_size
    dist.all_gather_object(all_results, local_result)

    if rank == 0:
        passed = all(
            result is not None and result["mismatch_iterations"] == 0
            for result in all_results
        )
        result_document = {
            "passed": passed,
            "backend": "xccl",
            "world_size": world_size,
            "mode": args.mode,
            "queue_test": (
                "torch.xpu.XPUGraph" if args.mode == "graph" else "direct"
            ),
            "ranks": all_results,
        }
        rendered = json.dumps(result_document, indent=2, sort_keys=True)
        print(rendered)
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered + "\n")
    dist.destroy_process_group()
    return 0 if mismatch_iterations == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
