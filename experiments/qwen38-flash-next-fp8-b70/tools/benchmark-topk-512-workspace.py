#!/usr/bin/env python3
"""Benchmark the Qwen3.8 512-expert M1 top-k workspace treatment."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import statistics
import time
from pathlib import Path

import torch


def load_extension(path: Path) -> None:
    spec = importlib.util.spec_from_file_location("vllm_xpu_kernels._moe_C", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load extension: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)


def tensor_digest(tensor: torch.Tensor) -> str:
    return hashlib.sha256(tensor.contiguous().cpu().numpy().tobytes()).hexdigest()


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1, int(len(ordered) * fraction) - 1))]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260830)
    parser.add_argument("--warmups", type=int, default=100)
    parser.add_argument("--submission-repeats", type=int, default=2000)
    parser.add_argument("--synchronized-repeats", type=int, default=500)
    parser.add_argument("--hash-repeats", type=int, default=100)
    parser.add_argument(
        "--scoring-function", choices=("softmax", "sigmoid"), default="softmax"
    )
    args = parser.parse_args()

    load_extension(args.library.resolve())
    torch.manual_seed(args.seed)
    gating_output = torch.randn((1, 512), dtype=torch.bfloat16, device="xpu")
    topk_weights = torch.empty((1, 10), dtype=torch.float32, device="xpu")
    topk_indices = torch.empty((1, 10), dtype=torch.int32, device="xpu")
    token_expert_indices = torch.empty((1, 10), dtype=torch.int32, device="xpu")

    def invoke() -> None:
        if args.scoring_function == "softmax":
            torch.ops._moe_C.topk_softmax(
                topk_weights,
                topk_indices,
                token_expert_indices,
                gating_output,
                True,
                None,
                None,
            )
        else:
            torch.ops._moe_C.topk_sigmoid(
                topk_weights,
                topk_indices,
                token_expert_indices,
                gating_output,
                True,
                None,
                1.0,
                None,
            )

    for _ in range(args.warmups):
        invoke()
    torch.xpu.synchronize()

    hashes: set[tuple[str, str, str]] = set()
    for _ in range(args.hash_repeats):
        invoke()
        torch.xpu.synchronize()
        hashes.add(
            (
                tensor_digest(topk_weights),
                tensor_digest(topk_indices),
                tensor_digest(token_expert_indices),
            )
        )

    submission_us: list[float] = []
    for ordinal in range(args.submission_repeats):
        start = time.perf_counter_ns()
        invoke()
        submission_us.append((time.perf_counter_ns() - start) / 1000)
        if (ordinal + 1) % 50 == 0:
            torch.xpu.synchronize()
    torch.xpu.synchronize()

    synchronized_us: list[float] = []
    for _ in range(args.synchronized_repeats):
        start = time.perf_counter_ns()
        invoke()
        torch.xpu.synchronize()
        synchronized_us.append((time.perf_counter_ns() - start) / 1000)

    print(
        json.dumps(
            {
                "schema_version": 1,
                "library": str(args.library.resolve()),
                "library_sha256": hashlib.sha256(args.library.read_bytes()).hexdigest(),
                "selector": os.environ.get(
                    "VLLM_XPU_TOPK_512_SKIP_UNUSED_WORKSPACE", ""
                ),
                "seed": args.seed,
                "scoring_function": args.scoring_function,
                "shape": {"tokens": 1, "experts": 512, "topk": 10},
                "unique_output_tuples": len(hashes),
                "output_tuples": sorted([list(item) for item in hashes]),
                "submission_us": {
                    "median": statistics.median(submission_us),
                    "p95": percentile(submission_us, 0.95),
                    "mean": statistics.mean(submission_us),
                },
                "synchronized_us": {
                    "median": statistics.median(synchronized_us),
                    "p95": percentile(synchronized_us, 0.95),
                    "mean": statistics.mean(synchronized_us),
                },
                "repeats": {
                    "warmups": args.warmups,
                    "hash": args.hash_repeats,
                    "submission": args.submission_repeats,
                    "synchronized": args.synchronized_repeats,
                },
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
