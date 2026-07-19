#!/usr/bin/env python3
"""Exactness and latency gate for the real DSpark W2 BF16 DPAS kernel."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import time

import torch
from safetensors import safe_open
import vllm_xpu_kernels._xpu_C  # noqa: F401


W1_NAME = "mtp.2.markov_head.markov_w1.weight"
W2_NAME = "mtp.2.markov_head.markov_w2.weight"
PARTITION = 129280 // 4


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = fraction * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def summarize(values: list[float]) -> dict[str, float]:
    return {
        "min_us": min(values),
        "p10_us": percentile(values, 0.10),
        "median_us": statistics.median(values),
        "mean_us": statistics.fmean(values),
        "p90_us": percentile(values, 0.90),
        "max_us": max(values),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--rank", type=int, default=0)
    parser.add_argument("--warmups", type=int, default=20)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.rank < 0 or args.rank >= 4:
        parser.error("rank must be in [0,4)")

    torch.xpu.set_device(0)
    device = torch.device("xpu:0")
    with safe_open(args.weights, framework="pt", device="cpu") as handle:
        w1 = handle.get_tensor(W1_NAME).contiguous()
        w2 = handle.get_tensor(W2_NAME).contiguous()
    packed = (
        w2.narrow(0, args.rank * PARTITION, PARTITION)
        .t()
        .contiguous()
        .to(device)
    )
    tokens = [
        17,
        PARTITION + 23,
        2 * PARTITION + 31,
        129280 - 19,
        97,
        4421,
        127999,
    ]
    activations = [w1[token].view(1, 256).to(device) for token in tokens]
    del w1, w2

    reference = torch.empty((1, PARTITION), dtype=torch.bfloat16, device=device)
    candidate = torch.empty_like(reference)
    base_generator = torch.Generator(device="cpu").manual_seed(0xB70D5A7)
    base = torch.randn(
        (1, PARTITION), generator=base_generator, dtype=torch.bfloat16
    ).to(device)
    lanes: dict[str, object] = {}
    passed = True
    for tiles_per_item in (1, 2, 4, 8):
        exact_outputs = True
        exact_tokens = True
        mismatch_elements = 0
        max_abs_error = 0.0
        for activation in activations:
            torch.mm(activation, packed, out=reference)
            torch.ops._xpu_C.deepseek_markov_m1_bf16_dpas_out(
                candidate, activation, packed, tiles_per_item
            )
            torch.xpu.synchronize()
            exact_outputs = exact_outputs and torch.equal(reference, candidate)
            different = int(torch.count_nonzero(reference != candidate).item())
            mismatch_elements += different
            if different:
                error = float(
                    (reference.float() - candidate.float()).abs().max().item()
                )
                max_abs_error = max(max_abs_error, error)
            reference_token = int((reference + base).argmax().item())
            candidate_token = int((candidate + base).argmax().item())
            exact_tokens = exact_tokens and reference_token == candidate_token

        reference_us: list[float] = []
        candidate_us: list[float] = []
        total = args.warmups + args.iterations
        for iteration in range(total):
            activation = activations[iteration % len(activations)]
            start_ns = time.perf_counter_ns()
            torch.mm(activation, packed, out=reference)
            torch.xpu.synchronize()
            ref_elapsed = (time.perf_counter_ns() - start_ns) / 1000.0
            start_ns = time.perf_counter_ns()
            torch.ops._xpu_C.deepseek_markov_m1_bf16_dpas_out(
                candidate, activation, packed, tiles_per_item
            )
            torch.xpu.synchronize()
            candidate_elapsed = (time.perf_counter_ns() - start_ns) / 1000.0
            if iteration >= args.warmups:
                reference_us.append(ref_elapsed)
                candidate_us.append(candidate_elapsed)

        reference_summary = summarize(reference_us)
        candidate_summary = summarize(candidate_us)
        speedup = (
            reference_summary["median_us"] / candidate_summary["median_us"]
        )
        lane_passed = exact_outputs and exact_tokens and speedup >= 1.10
        passed = passed and lane_passed
        lanes[str(tiles_per_item)] = {
            "passed": lane_passed,
            "exact_outputs": exact_outputs,
            "exact_argmax_tokens": exact_tokens,
            "mismatch_elements": mismatch_elements,
            "max_abs_error": max_abs_error,
            "reference": reference_summary,
            "candidate": candidate_summary,
            "median_speedup": speedup,
        }

    # Only one exact, faster tile geometry is required for promotion.
    passing_lanes = [name for name, lane in lanes.items() if lane["passed"]]
    result = {
        "schema_version": 1,
        "classification": "deepseek_v4_dspark_markov_w2_bf16_dpas_gate",
        "passed": bool(passing_lanes),
        "passing_lanes": passing_lanes,
        "rank": args.rank,
        "weights": str(args.weights),
        "warmups": args.warmups,
        "iterations": args.iterations,
        "lanes": lanes,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
