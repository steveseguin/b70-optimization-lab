#!/usr/bin/env python3
"""Gate Xe2 MXFP4 N-tile policies on production verifier widths."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics

import torch

import vllm  # noqa: F401
import vllm._custom_ops  # noqa: F401
import vllm_xpu_kernels  # noqa: F401
from vllm_xpu_kernels.fused_moe_interface import XpuFusedMoe


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-policy", choices=("32", "128"), required=True)
    parser.add_argument("--ep-rank", type=int, choices=range(4), required=True)
    parser.add_argument("--width", type=int, choices=(2, 4, 8), default=2)
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--warmup", type=int, default=30)
    parser.add_argument("--samples", type=int, default=9)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--required-ms", type=float, default=0.50)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    torch.manual_seed(20260716 + args.ep_rank)
    torch.xpu.manual_seed_all(20260716 + args.ep_rank)
    device = torch.device("xpu:0")
    hidden_size = 4096
    intermediate_size = 2048
    local_experts = 40
    global_experts = 160
    topk = 6
    ep_size = 4
    local_base = args.ep_rank * local_experts

    hidden = (
        torch.randn((args.width, hidden_size), device=device, dtype=torch.bfloat16)
        / 16
    )
    w13 = torch.randint(
        0,
        256,
        (local_experts, 2 * intermediate_size, hidden_size // 2),
        device=device,
        dtype=torch.uint8,
    ).view(torch.float4_e2m1fn_x2)
    w2 = torch.randint(
        0,
        256,
        (local_experts, hidden_size, intermediate_size // 2),
        device=device,
        dtype=torch.uint8,
    ).view(torch.float4_e2m1fn_x2)
    w13_scale = torch.randint(
        119,
        123,
        (local_experts, 2 * intermediate_size, hidden_size // 32),
        device=device,
        dtype=torch.uint8,
    )
    w2_scale = torch.randint(
        119,
        123,
        (local_experts, hidden_size, intermediate_size // 32),
        device=device,
        dtype=torch.uint8,
    )
    topk_ids = torch.empty((args.width, topk), device=device, dtype=torch.int32)
    weight_rows = [
        [0.405, 0.325, 0.275, 0.205, 0.145, 0.115],
        [0.465, 0.345, 0.255, 0.195, 0.135, 0.105],
    ]
    topk_weights = torch.tensor(
        [weight_rows[row % len(weight_rows)] for row in range(args.width)],
        device=device,
        dtype=torch.float32,
    )
    reference_output = torch.empty_like(hidden)
    candidate_output = torch.empty_like(hidden)
    routed = XpuFusedMoe(
        w13=w13,
        w13_scales=w13_scale,
        w13_bias=None,
        w2=w2,
        w2_scales=w2_scale,
        w2_bias=None,
        n_experts_per_token=topk,
        activation="swigluoai",
        num_experts=local_experts,
        ep_rank=args.ep_rank,
        ep_size=ep_size,
        gemm1_clamp_limit=10.0,
    )

    remote = [rank * local_experts for rank in range(ep_size) if rank != args.ep_rank]
    lb = local_base
    def local_expert(offset: int) -> int:
        return lb + offset % local_experts

    route_patterns = {
        "same_typical": [
            [local_expert(i) for i in range(3)] + remote for _ in range(args.width)
        ],
        "disjoint_typical": [
            [local_expert(3 * row + i) for i in range(3)]
            + [base + row % local_experts for base in remote]
            for row in range(args.width)
        ],
        "cross_row_overlap": [
            [local_expert(row + i) for i in range(3)]
            + [base + row % local_experts for base in remote]
            for row in range(args.width)
        ],
        "six_local": [
            [local_expert(6 * row + i) for i in range(6)]
            for row in range(args.width)
        ],
    }

    def call(output: torch.Tensor) -> None:
        routed.apply(output, hidden, topk_weights, topk_ids)

    def capture(policy: str, output: torch.Tensor) -> torch.xpu.XPUGraph:
        os.environ["VLLM_XPU_MXFP4_SMALL_M_N"] = policy
        for _ in range(3):
            call(output)
        torch.xpu.synchronize()
        graph = torch.xpu.XPUGraph()
        with torch.xpu.graph(graph):
            call(output)
        graph.replay()
        torch.xpu.synchronize()
        return graph

    topk_ids.copy_(torch.tensor(route_patterns["same_typical"], device=device))
    reference_graph = capture("64", reference_output)
    candidate_graph = capture(args.candidate_policy, candidate_output)

    correctness = []
    for pattern_index, (pattern_name, pattern) in enumerate(route_patterns.items()):
        topk_ids.copy_(torch.tensor(pattern, device=device, dtype=torch.int32))
        for epoch in range(args.epochs):
            generator = torch.Generator(device=device).manual_seed(
                20260716 + args.ep_rank * 1000 + pattern_index * 100 + epoch
            )
            hidden.copy_(
                torch.randn(
                    hidden.shape,
                    device=device,
                    dtype=hidden.dtype,
                    generator=generator,
                )
                / 16
            )
            reference_graph.replay()
            candidate_graph.replay()
            torch.xpu.synchronize()
            diff = (reference_output.float() - candidate_output.float()).abs()
            correctness.append(
                {
                    "pattern": pattern_name,
                    "epoch": epoch,
                    "exact": torch.equal(reference_output, candidate_output),
                    "mismatch_count": int(
                        torch.count_nonzero(reference_output != candidate_output).item()
                    ),
                    "max_abs": float(diff.max().item()),
                }
            )

    topk_ids.copy_(torch.tensor(route_patterns["disjoint_typical"], device=device))
    for _ in range(args.warmup):
        reference_graph.replay()
        candidate_graph.replay()
    torch.xpu.synchronize()

    def timed_us(graph: torch.xpu.XPUGraph) -> float:
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(args.iterations):
            graph.replay()
        end.record()
        end.synchronize()
        return start.elapsed_time(end) * 1000.0 / args.iterations

    reference_samples = []
    candidate_samples = []
    for sample in range(args.samples):
        if sample % 2 == 0:
            reference_samples.append(timed_us(reference_graph))
            candidate_samples.append(timed_us(candidate_graph))
        else:
            candidate_samples.append(timed_us(candidate_graph))
            reference_samples.append(timed_us(reference_graph))
    reference_us = statistics.median(reference_samples)
    candidate_us = statistics.median(candidate_samples)
    saved_ms = (reference_us - candidate_us) * 43 / 1000.0
    exact = all(row["exact"] for row in correctness)
    result = {
        "schema_version": 1,
        "classification": "deepseek_v4_mxfp4_verifier_n_policy_gate",
        "device": torch.xpu.get_device_name(device),
        "logical_device": str(device),
        "ep_rank": args.ep_rank,
        "candidate_policy": args.candidate_policy,
        "shape": {
            "m": args.width,
            "hidden_size": hidden_size,
            "intermediate_size": intermediate_size,
            "local_experts": local_experts,
            "global_experts": global_experts,
            "topk": topk,
        },
        "correctness": {
            "cases": len(correctness),
            "exact_cases": sum(row["exact"] for row in correctness),
            "passed": exact,
            "rows": correctness,
        },
        "timing": {
            "route": "disjoint_typical",
            "n64_median_us": reference_us,
            "candidate_median_us": candidate_us,
            "speedup": reference_us / candidate_us,
            "saved_us_per_layer": reference_us - candidate_us,
            "projected_saved_ms_per_43_layers": saved_ms,
            "required_ms": args.required_ms,
            "clears_integration_gate": saved_ms >= args.required_ms,
            "n64_samples_us": reference_samples,
            "candidate_samples_us": candidate_samples,
        },
        "passed": exact and saved_ms >= args.required_ms,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "correctness"}, indent=2))
    reference_graph.reset()
    candidate_graph.reset()
    torch.xpu.synchronize()
    return 0 if exact else 1


if __name__ == "__main__":
    raise SystemExit(main())
