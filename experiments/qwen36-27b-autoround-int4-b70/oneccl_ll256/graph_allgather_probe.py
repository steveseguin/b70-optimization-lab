#!/usr/bin/env python3
"""Exact TP2 XPU-graph replay probe for Qwen's draft all-gather.

The TP2 Qwen3 Next MTP layer sequence-parallelizes its MoE and gathers BF16
``[rows, 2560]`` rank-local outputs before the next draft operation.  The
compiled draft graph currently lowers this to a functional all-gather followed
by ``wait_tensor``, which fails during XPU command-graph capture.  This probe
tests direct preallocated collective forms independently of vLLM and changes
the input on every replay so stale-buffer behavior cannot pass accidentally.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

import torch
import torch.distributed as dist


def _input_for_iteration(
    base: torch.Tensor,
    *,
    rank: int,
    iteration: int,
) -> torch.Tensor:
    # Integral values stay exactly representable in BF16.
    return base + rank * 37 + (iteration % 19)


def _expected_for_iteration(
    base: torch.Tensor,
    *,
    world_size: int,
    iteration: int,
) -> torch.Tensor:
    return torch.cat(
        [
            _input_for_iteration(base, rank=rank, iteration=iteration)
            for rank in range(world_size)
        ],
        dim=0,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--capture-mode",
        choices=("blocking", "async-wait", "async-no-wait"),
        default="blocking",
    )
    parser.add_argument("--rows", type=int, default=4)
    parser.add_argument("--hidden-size", type=int, default=2560)
    parser.add_argument("--warmup", type=int, default=8)
    parser.add_argument("--iterations", type=int, default=512)
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
    static_output = torch.empty(
        (args.rows * world_size, args.hidden_size),
        dtype=torch.bfloat16,
        device=device,
    )

    for iteration in range(args.warmup):
        static_input.copy_(
            _input_for_iteration(base, rank=rank, iteration=iteration)
        )
        dist.all_gather_into_tensor(static_output, static_input)
    torch.xpu.synchronize()
    dist.barrier()

    graph = torch.xpu.XPUGraph()
    static_input.copy_(_input_for_iteration(base, rank=rank, iteration=0))
    torch.xpu.synchronize()
    dist.barrier()
    capture_error: str | None = None
    try:
        with torch.xpu.graph(graph):
            if args.capture_mode == "blocking":
                dist.all_gather_into_tensor(static_output, static_input)
            else:
                work = dist.all_gather_into_tensor(
                    static_output, static_input, async_op=True
                )
                if args.capture_mode == "async-wait":
                    work.wait()
        torch.xpu.synchronize()
        dist.barrier()
    except Exception as exc:
        capture_error = repr(exc)

    first_mismatch: dict[str, Any] | None = None
    mismatch_iterations = 0
    max_abs_diff = 0.0
    completed_iterations = 0
    if capture_error is None:
        for iteration in range(args.iterations):
            static_input.copy_(
                _input_for_iteration(base, rank=rank, iteration=iteration)
            )
            # Publish the new fixed-address input before replay. The endpoint
            # graph wrapper performs the equivalent input handoff.
            torch.xpu.synchronize()
            graph.replay()
            torch.xpu.synchronize()
            completed_iterations += 1

            expected = _expected_for_iteration(
                base, world_size=world_size, iteration=iteration
            )
            if not torch.equal(static_output, expected):
                mismatch_iterations += 1
                diff = (static_output.float() - expected.float()).abs()
                iteration_max = float(diff.max().item())
                max_abs_diff = max(max_abs_diff, iteration_max)
                if first_mismatch is None:
                    mismatch_flat = diff.reshape(-1).nonzero().reshape(-1)
                    first_index = int(mismatch_flat[0].item())
                    first_mismatch = {
                        "iteration": iteration,
                        "flat_index": first_index,
                        "actual": float(
                            static_output.reshape(-1)[first_index].item()
                        ),
                        "expected": float(expected.reshape(-1)[first_index].item()),
                        "max_abs_diff": iteration_max,
                        "mismatch_elements": int(mismatch_flat.numel()),
                    }

    loaded_ccl_paths = sorted(
        {
            line.rsplit(maxsplit=1)[-1]
            for line in Path("/proc/self/maps").read_text().splitlines()
            if "libccl.so" in line
            and line.rsplit(maxsplit=1)[-1].startswith("/")
        }
    )
    local_result = {
        "rank": rank,
        "local_rank": local_rank,
        "device": str(device),
        "rows": args.rows,
        "hidden_size": args.hidden_size,
        "dtype": "bfloat16",
        "capture_mode": args.capture_mode,
        "requested_iterations": args.iterations,
        "completed_iterations": completed_iterations,
        "loaded_ccl_paths": loaded_ccl_paths,
        "capture_error": capture_error,
        "mismatch_iterations": mismatch_iterations,
        "first_mismatch": first_mismatch,
        "max_abs_diff": max_abs_diff,
    }
    all_results: list[dict[str, Any] | None] = [None] * world_size
    dist.all_gather_object(all_results, local_result)

    failed = capture_error is not None or mismatch_iterations != 0
    if rank == 0:
        passed = all(
            result is not None
            and result["capture_error"] is None
            and result["mismatch_iterations"] == 0
            and result["completed_iterations"] == args.iterations
            for result in all_results
        )
        result_document = {
            "passed": passed,
            "backend": "xccl",
            "world_size": world_size,
            "queue_test": "torch.xpu.XPUGraph",
            "capture_mode": args.capture_mode,
            "ranks": all_results,
        }
        rendered = json.dumps(result_document, indent=2, sort_keys=True)
        print(rendered)
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered + "\n")
    dist.destroy_process_group()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
