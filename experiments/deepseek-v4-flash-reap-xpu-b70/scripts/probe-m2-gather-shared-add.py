#!/usr/bin/env python3
"""Isolate fixed-M2 gather/shared-add fusion on one B70.

The control is the production generic gather followed by a BF16 add. The
candidate preserves the gather's BF16 rounding point and writes the combined
result in one submission. Both paths use fixed addresses under XPU graph
replay, and correctness is checked with changing inputs and route maps.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics

import torch

import vllm  # noqa: F401
import vllm._custom_ops  # noqa: F401
import vllm_xpu_kernels  # noqa: F401


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ep-rank", type=int, choices=range(4), required=True)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=30)
    parser.add_argument("--samples", type=int, default=11)
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--required-ms", type=float, default=0.25)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    seed = 20260716 + args.ep_rank * 1000
    torch.manual_seed(seed)
    torch.xpu.manual_seed_all(seed)
    device = torch.device("xpu:0")
    hidden_size = 4096
    topk = 6
    num_tokens = 2
    num_slots = num_tokens * topk

    moe_output = torch.randn(
        (num_slots, hidden_size), device=device, dtype=torch.bfloat16
    ) / 16
    shared_output = torch.randn(
        (num_tokens, hidden_size), device=device, dtype=torch.bfloat16
    ) / 16
    topk_weights = torch.tensor(
        [
            [0.405, 0.325, 0.275, 0.205, 0.145, 0.115],
            [0.465, 0.345, 0.255, 0.195, 0.135, 0.105],
        ],
        device=device,
        dtype=torch.float32,
    )
    route_map = torch.empty((num_tokens, topk), device=device, dtype=torch.int32)
    routed_output = torch.empty_like(shared_output)
    baseline_output = torch.empty_like(shared_output)
    candidate_output = torch.empty_like(shared_output)
    alias_output = torch.empty_like(shared_output)

    route_patterns = {
        "same_typical": [[0, 1, 2, -1, -1, -1], [0, 1, 2, -1, -1, -1]],
        "disjoint_typical": [[0, 1, 2, -1, -1, -1], [3, 4, 5, -1, -1, -1]],
        "cross_row_overlap": [[0, 1, 2, -1, -1, -1], [1, 2, 3, -1, -1, -1]],
        "duplicate_slots": [[0, 0, 1, -1, -1, -1], [2, 2, 3, -1, -1, -1]],
        "single_local": [[0, -1, -1, -1, -1, -1], [1, -1, -1, -1, -1, -1]],
        "six_local": [[0, 1, 2, 3, 4, 5], [6, 7, 8, 9, 10, 11]],
        "all_remote": [[-1, -1, -1, -1, -1, -1], [-1, -1, -1, -1, -1, -1]],
    }

    def baseline() -> None:
        torch.ops._moe_C.moe_gather(
            routed_output, moe_output, topk_weights, route_map, 40
        )
        torch.add(routed_output, shared_output, out=baseline_output)

    def candidate() -> None:
        torch.ops._moe_C.moe_gather_shared_add_m2(
            candidate_output,
            moe_output,
            shared_output,
            topk_weights,
            route_map,
            40,
        )

    def candidate_alias() -> None:
        torch.ops._moe_C.moe_gather_shared_add_m2(
            alias_output,
            moe_output,
            alias_output,
            topk_weights,
            route_map,
            40,
        )

    def capture(fn) -> torch.xpu.XPUGraph:
        for _ in range(3):
            fn()
        torch.xpu.synchronize()
        graph = torch.xpu.XPUGraph()
        with torch.xpu.graph(graph):
            fn()
        graph.replay()
        torch.xpu.synchronize()
        return graph

    route_map.copy_(torch.tensor(route_patterns["disjoint_typical"], device=device))
    baseline_graph = capture(baseline)
    candidate_graph = capture(candidate)
    alias_graph = capture(candidate_alias)

    correctness = []
    for pattern_index, (pattern_name, pattern) in enumerate(route_patterns.items()):
        route_map.copy_(torch.tensor(pattern, device=device, dtype=torch.int32))
        for epoch in range(args.epochs):
            generator = torch.Generator(device=device).manual_seed(
                seed + pattern_index * 100 + epoch
            )
            moe_output.copy_(
                torch.randn(
                    moe_output.shape,
                    device=device,
                    dtype=moe_output.dtype,
                    generator=generator,
                )
                / 16
            )
            shared_output.copy_(
                torch.randn(
                    shared_output.shape,
                    device=device,
                    dtype=shared_output.dtype,
                    generator=generator,
                )
                / 16
            )
            baseline_graph.replay()
            candidate_graph.replay()
            torch.xpu.synchronize()
            nonalias_exact = torch.equal(baseline_output, candidate_output)

            alias_output.copy_(shared_output)
            alias_graph.replay()
            torch.xpu.synchronize()
            alias_exact = torch.equal(baseline_output, alias_output)
            correctness.append(
                {
                    "pattern": pattern_name,
                    "epoch": epoch,
                    "nonalias_exact": nonalias_exact,
                    "alias_exact": alias_exact,
                    "nonalias_mismatch_count": int(
                        torch.count_nonzero(baseline_output != candidate_output).item()
                    ),
                    "alias_mismatch_count": int(
                        torch.count_nonzero(baseline_output != alias_output).item()
                    ),
                }
            )

    def timed_us(graph: torch.xpu.XPUGraph) -> float:
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(args.iterations):
            graph.replay()
        end.record()
        end.synchronize()
        return start.elapsed_time(end) * 1000.0 / args.iterations

    timings = {}
    for pattern_name, pattern in route_patterns.items():
        route_map.copy_(torch.tensor(pattern, device=device, dtype=torch.int32))
        for _ in range(args.warmup):
            baseline_graph.replay()
            candidate_graph.replay()
        torch.xpu.synchronize()
        baseline_samples = []
        candidate_samples = []
        for sample in range(args.samples):
            if sample % 2 == 0:
                baseline_samples.append(timed_us(baseline_graph))
                candidate_samples.append(timed_us(candidate_graph))
            else:
                candidate_samples.append(timed_us(candidate_graph))
                baseline_samples.append(timed_us(baseline_graph))
        baseline_us = statistics.median(baseline_samples)
        candidate_us = statistics.median(candidate_samples)
        timings[pattern_name] = {
            "baseline_median_us": baseline_us,
            "candidate_median_us": candidate_us,
            "saved_us_per_layer": baseline_us - candidate_us,
            "projected_saved_ms_per_43_layers": (
                baseline_us - candidate_us
            ) * 43 / 1000.0,
            "baseline_samples_us": baseline_samples,
            "candidate_samples_us": candidate_samples,
        }

    exact = all(
        row["nonalias_exact"] and row["alias_exact"] for row in correctness
    )
    conservative_ms = min(
        row["projected_saved_ms_per_43_layers"] for row in timings.values()
    )
    result = {
        "schema_version": 1,
        "classification": "deepseek_v4_m2_gather_shared_add_isolated_gate",
        "device": torch.xpu.get_device_name(device),
        "ep_rank": args.ep_rank,
        "shape": {"tokens": 2, "topk": 6, "hidden_size": hidden_size},
        "correctness": {
            "cases": len(correctness),
            "exact_cases": sum(
                row["nonalias_exact"] and row["alias_exact"]
                for row in correctness
            ),
            "passed": exact,
            "rows": correctness,
        },
        "timing": {
            "patterns": timings,
            "conservative_projected_saved_ms_per_43_layers": conservative_ms,
            "required_ms": args.required_ms,
            "clears_portfolio_service_gate": conservative_ms >= args.required_ms,
        },
        "passed": exact and conservative_ms >= args.required_ms,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "device": result["device"],
                "ep_rank": args.ep_rank,
                "correctness": result["correctness"],
                "timing": result["timing"],
                "passed": result["passed"],
            },
            indent=2,
        )
    )
    baseline_graph.reset()
    candidate_graph.reset()
    alias_graph.reset()
    torch.xpu.synchronize()
    return 0 if exact else 1


if __name__ == "__main__":
    raise SystemExit(main())
