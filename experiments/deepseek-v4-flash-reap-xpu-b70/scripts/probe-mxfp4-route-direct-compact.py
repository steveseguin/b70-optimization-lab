#!/usr/bin/env python3
"""Gate the complete M=2/4/8 route-direct MXFP4 production boundary.

The reference and candidate both execute remap, two grouped GEMMs, clamped
SwiGLU, and the canonical gather.  Only the grouped-GEMM scheduler changes.
Correctness includes changing inputs and hostile routing patterns after graph
capture; timing includes the same complete boundary.
"""

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


MAX_M_ENV = "VLLM_XPU_V4_ROUTE_DIRECT_COMPACT_MAX_M"
OLD_M2_ENV = "VLLM_XPU_V4_M2_ROUTE_DIRECT_COMPACT"
CLAMP_ENV = "VLLM_XPU_V4_M2_ROUTED_CLAMP_SILU"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ep-rank", type=int, choices=range(4), required=True)
    parser.add_argument("--width", type=int, choices=(2, 4, 8), default=8)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--samples", type=int, default=9)
    parser.add_argument("--iterations", type=int, default=80)
    parser.add_argument("--required-ms", type=float, default=0.50)
    parser.add_argument(
        "--compact-route-lanes", type=int, choices=(4, 48), default=48
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    # The promoted endpoint uses N128.  Fail closed against inherited state.
    os.environ["VLLM_XPU_MXFP4_SMALL_M_N"] = "128"
    os.environ["VLLM_XPU_M2_COMPACT_ROUTE_LANES"] = str(
        args.compact_route_lanes
    )
    os.environ[OLD_M2_ENV] = "0"
    os.environ[CLAMP_ENV] = "1"

    torch.manual_seed(20260718 + args.ep_rank)
    torch.xpu.manual_seed_all(20260718 + args.ep_rank)
    device = torch.device("xpu:0")
    width = args.width
    topk = 6
    local_experts = 40
    global_experts = 160
    local_base = args.ep_rank * local_experts
    local = [local_base + index for index in range(local_experts)]
    remote = [
        expert
        for expert in range(global_experts)
        if not local_base <= expert < local_base + local_experts
    ]
    expert_map = torch.full(
        (global_experts,), -1, device=device, dtype=torch.int32
    )
    expert_map[local_base : local_base + local_experts] = torch.arange(
        local_experts, device=device, dtype=torch.int32
    )

    def typical_row(row: int, overlap: bool = False) -> list[int]:
        local_count = 1 + (row & 1)
        local_seed = 0 if overlap else row * 3
        local_routes = [
            local[(local_seed + slot) % len(local)]
            for slot in range(local_count)
        ]
        remote_routes = [
            remote[(row * 11 + slot * 7) % len(remote)]
            for slot in range(topk - local_count)
        ]
        return local_routes + remote_routes

    route_patterns = {
        "typical_quarter_local": [typical_row(row) for row in range(width)],
        "overlap_quarter_local": [
            typical_row(row, overlap=True) for row in range(width)
        ],
        "six_local": [
            [local[(row * topk + slot) % len(local)] for slot in range(topk)]
            for row in range(width)
        ],
        "all_same_local": [[local[0]] * topk for _ in range(width)],
        "all_remote": [
            [remote[(row * topk + slot) % len(remote)] for slot in range(topk)]
            for row in range(width)
        ],
    }

    def make_weight(n: int, k: int) -> tuple[torch.Tensor, torch.Tensor]:
        packed = torch.randint(
            0,
            256,
            (local_experts, n, k // 2),
            device=device,
            dtype=torch.uint8,
        ).view(torch.float4_e2m1fn_x2)
        scales = torch.randint(
            119,
            123,
            (local_experts, n, k // 32),
            device=device,
            dtype=torch.uint8,
        )
        return packed, scales

    n = 4096
    k1 = 4096
    k2 = 2048
    weight1, scale1 = make_weight(n, k1)
    weight2, scale2 = make_weight(n, k2)
    hidden = torch.randn(
        (width, k1), device=device, dtype=torch.bfloat16
    ) / 16
    topk_ids = torch.empty((width, topk), device=device, dtype=torch.int32)
    topk_weights = torch.rand(
        (width, topk), device=device, dtype=torch.float32
    )
    topk_weights.div_(topk_weights.sum(dim=1, keepdim=True))
    reference_output = torch.empty(
        (width, n), device=device, dtype=torch.bfloat16
    )
    candidate_output = torch.empty_like(reference_output)

    def make_moe(max_m: int) -> XpuFusedMoe:
        os.environ[MAX_M_ENV] = str(max_m)
        return XpuFusedMoe(
            weight1,
            scale1,
            None,
            weight2,
            scale2,
            None,
            topk,
            "silu",
            local_experts,
            ep_rank=args.ep_rank,
            ep_size=4,
            expert_map=expert_map,
            gemm1_clamp_limit=10.0,
        )

    reference_moe = make_moe(0)
    candidate_moe = make_moe(width)

    def reference_call() -> None:
        reference_moe.apply(
            reference_output, hidden, topk_weights, topk_ids, expert_map
        )

    def candidate_call() -> None:
        candidate_moe.apply(
            candidate_output, hidden, topk_weights, topk_ids, expert_map
        )

    def capture(callable_) -> torch.xpu.XPUGraph:
        for _ in range(3):
            callable_()
        torch.xpu.synchronize()
        graph = torch.xpu.XPUGraph()
        with torch.xpu.graph(graph):
            callable_()
        graph.replay()
        torch.xpu.synchronize()
        return graph

    topk_ids.copy_(
        torch.tensor(
            route_patterns["typical_quarter_local"],
            device=device,
            dtype=torch.int32,
        )
    )
    reference_graph = capture(reference_call)
    candidate_graph = capture(candidate_call)

    correctness = []
    for pattern_index, (pattern_name, pattern) in enumerate(
        route_patterns.items()
    ):
        topk_ids.copy_(
            torch.tensor(pattern, device=device, dtype=torch.int32)
        )
        for epoch in range(args.epochs):
            generator = torch.Generator(device=device).manual_seed(
                20260718
                + args.ep_rank * 10000
                + pattern_index * 100
                + epoch
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
            weights = torch.rand(
                topk_weights.shape,
                device=device,
                dtype=topk_weights.dtype,
                generator=generator,
            )
            weights.div_(weights.sum(dim=1, keepdim=True))
            topk_weights.copy_(weights)
            reference_graph.replay()
            candidate_graph.replay()
            torch.xpu.synchronize()
            exact = torch.equal(reference_output, candidate_output)
            max_abs_diff = float(
                (reference_output.float() - candidate_output.float())
                .abs()
                .max()
                .item()
            )
            correctness.append(
                {
                    "pattern": pattern_name,
                    "epoch": epoch,
                    "exact": exact,
                    "max_abs_diff": max_abs_diff,
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

    timing_rows = []
    for pattern_name, pattern in route_patterns.items():
        topk_ids.copy_(
            torch.tensor(pattern, device=device, dtype=torch.int32)
        )
        for _ in range(args.warmup):
            reference_graph.replay()
            candidate_graph.replay()
        torch.xpu.synchronize()
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
        timing_rows.append(
            {
                "route": pattern_name,
                "reference_median_us": reference_us,
                "candidate_median_us": candidate_us,
                "speedup": reference_us / candidate_us,
                "saved_us_per_layer": reference_us - candidate_us,
                "projected_saved_ms_per_43_layers": (
                    reference_us - candidate_us
                )
                * 43
                / 1000.0,
                "reference_samples_us": reference_samples,
                "candidate_samples_us": candidate_samples,
            }
        )

    exact = all(row["exact"] for row in correctness)
    minimum_saved_ms = min(
        row["projected_saved_ms_per_43_layers"] for row in timing_rows
    )
    result = {
        "schema_version": 1,
        "classification": "deepseek_v4_mxfp4_route_direct_compact_gate",
        "device": torch.xpu.get_device_name(device),
        "logical_device": str(device),
        "ep_rank": args.ep_rank,
        "policy": "N128",
        "compact_route_lanes": args.compact_route_lanes,
        "shape": {
            "m": width,
            "gemm1": {"n": n, "k": k1},
            "gemm2": {"n": n, "k": k2},
            "local_experts": local_experts,
            "global_experts": global_experts,
            "topk": topk,
        },
        "boundary": "remap+gemm1+clamped_swiglu+gemm2+canonical_gather",
        "correctness": {
            "cases": len(correctness),
            "exact_cases": sum(row["exact"] for row in correctness),
            "passed": exact,
            "rows": correctness,
        },
        "timing": {
            "selection_rule": "minimum savings across all declared patterns",
            "rows": timing_rows,
            "selected_minimum_saved_ms_per_43_layers": minimum_saved_ms,
            "required_ms": args.required_ms,
            "clears_integration_gate": minimum_saved_ms >= args.required_ms,
        },
        "passed": exact and minimum_saved_ms >= args.required_ms,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "ep_rank": args.ep_rank,
                "width": width,
                "exact": exact,
                "minimum_saved_ms_per_43_layers": minimum_saved_ms,
                "required_ms": args.required_ms,
                "passed": result["passed"],
                "timing": timing_rows,
            },
            indent=2,
        )
    )
    reference_graph.reset()
    candidate_graph.reset()
    torch.xpu.synchronize()
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
