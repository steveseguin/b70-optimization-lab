#!/usr/bin/env python3
"""Measure the graph-replay upper bound from deleting direct M=1 gather."""

from __future__ import annotations

import argparse
import json
import os
import statistics
from pathlib import Path

import torch

import vllm_xpu_kernels._moe_C  # noqa: F401
import vllm_xpu_kernels._xpu_C  # noqa: F401


HIDDEN_SIZE = 4096
INTERMEDIATE_SIZE = 2048
LOCAL_EXPERTS = 40
GLOBAL_EXPERTS = 160
TOPK = 6
MOE_LAYERS = 43


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--ep-rank", type=int, choices=range(4), required=True)
    parser.add_argument("--warmup", type=int, default=80)
    parser.add_argument("--iterations", type=int, default=400)
    parser.add_argument("--samples", type=int, default=11)
    parser.add_argument("--seed", type=int, default=99173)
    args = parser.parse_args()

    if os.environ.get("VLLM_XPU_MXFP4_SMALL_M_N") not in (None, "", "64"):
        raise RuntimeError("production gate requires the MXFP4 N64 policy")

    torch.manual_seed(args.seed + args.ep_rank)
    torch.xpu.manual_seed_all(args.seed + args.ep_rank)
    device = torch.device("xpu:0")

    activation = torch.randn(
        (TOPK, INTERMEDIATE_SIZE), dtype=torch.bfloat16, device=device
    )
    weights = torch.randint(
        0,
        256,
        (LOCAL_EXPERTS, HIDDEN_SIZE, INTERMEDIATE_SIZE // 2),
        dtype=torch.uint8,
        device=device,
    ).view(torch.float4_e2m1fn_x2)
    scales = torch.randint(
        119,
        123,
        (LOCAL_EXPERTS, HIDDEN_SIZE, INTERMEDIATE_SIZE // 32),
        dtype=torch.uint8,
        device=device,
    )
    topk_ids = torch.empty((1, TOPK), dtype=torch.int32, device=device)
    topk_weights = torch.tensor(
        [[0.465, 0.345, 0.255, 0.195, 0.135, 0.105]],
        dtype=torch.float32,
        device=device,
    )
    expert_map = torch.empty((GLOBAL_EXPERTS,), dtype=torch.int32, device=device)
    torch.ops._moe_C.init_expert_map(
        expert_map, LOCAL_EXPERTS, args.ep_rank, 4
    )
    gemm2_output = torch.empty(
        (TOPK, HIDDEN_SIZE), dtype=torch.bfloat16, device=device
    )
    final_output = torch.empty(
        (1, HIDDEN_SIZE), dtype=torch.bfloat16, device=device
    )

    def gemm2() -> None:
        torch.ops._xpu_C.cutlass_grouped_gemm_m1_topk_interface(
            activation,
            weights,
            scales,
            None,
            gemm2_output,
            topk_ids,
            expert_map,
            HIDDEN_SIZE,
            INTERMEDIATE_SIZE,
            LOCAL_EXPERTS,
            False,
        )

    def gather() -> None:
        torch.ops._moe_C.moe_gather_direct_m1(
            final_output,
            gemm2_output,
            topk_weights,
            topk_ids,
            expert_map,
            LOCAL_EXPERTS,
        )

    def gemm2_and_gather() -> None:
        gemm2()
        gather()

    local_base = args.ep_rank * LOCAL_EXPERTS
    remote = [rank * LOCAL_EXPERTS for rank in range(4) if rank != args.ep_rank]
    routes = {
        "2_local": [
            local_base,
            local_base + 1,
            remote[0],
            remote[1],
            remote[2],
            remote[0] + 1,
        ],
        "3_local": [
            local_base,
            local_base + 1,
            local_base + 2,
            remote[0],
            remote[1],
            remote[2],
        ],
        "4_local": [
            local_base,
            local_base + 1,
            local_base + 2,
            local_base + 3,
            remote[0],
            remote[1],
        ],
        "6_local": [local_base + offset for offset in range(TOPK)],
    }

    topk_ids.copy_(
        torch.tensor([routes["3_local"]], dtype=torch.int32, device=device)
    )
    for _ in range(4):
        gemm2_and_gather()
    torch.xpu.synchronize()
    gemm_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(gemm_graph):
        gemm2()
    combined_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(combined_graph):
        gemm2_and_gather()
    gather_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(gather_graph):
        gather()
    torch.xpu.synchronize()

    def time_graph(graph: torch.xpu.XPUGraph) -> float:
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(args.iterations):
            graph.replay()
        end.record()
        end.synchronize()
        return start.elapsed_time(end) * 1000.0 / args.iterations

    results: dict[str, object] = {}
    for route_name, route in routes.items():
        topk_ids.copy_(torch.tensor([route], dtype=torch.int32, device=device))
        for _ in range(args.warmup):
            gemm_graph.replay()
            combined_graph.replay()
            gather_graph.replay()
        torch.xpu.synchronize()
        gemm_samples: list[float] = []
        combined_samples: list[float] = []
        gather_samples: list[float] = []
        for sample in range(args.samples):
            order = (
                (gemm_graph, combined_graph, gather_graph)
                if sample % 2 == 0
                else (gather_graph, combined_graph, gemm_graph)
            )
            sample_values = {id(graph): time_graph(graph) for graph in order}
            gemm_samples.append(sample_values[id(gemm_graph)])
            combined_samples.append(sample_values[id(combined_graph)])
            gather_samples.append(sample_values[id(gather_graph)])
        gemm_median = statistics.median(gemm_samples)
        combined_median = statistics.median(combined_samples)
        gather_median = statistics.median(gather_samples)
        deleted_boundary_us = combined_median - gemm_median
        results[route_name] = {
            "route": route,
            "gemm2_median_us": gemm_median,
            "gemm2_plus_gather_median_us": combined_median,
            "gather_only_median_us": gather_median,
            "deleted_boundary_us": deleted_boundary_us,
            "projected_deleted_boundary_ms_per_token": (
                deleted_boundary_us * MOE_LAYERS / 1000.0
            ),
            "gemm2_samples_us": gemm_samples,
            "gemm2_plus_gather_samples_us": combined_samples,
            "gather_only_samples_us": gather_samples,
        }

    typical_projection = results["3_local"][
        "projected_deleted_boundary_ms_per_token"
    ]
    payload = {
        "classification": "deepseek_v4_m1_direct_gather_graph_upper_bound",
        "device": torch.xpu.get_device_name(),
        "torch": torch.__version__,
        "ep_rank": args.ep_rank,
        "shape": {
            "topk": TOPK,
            "hidden_size": HIDDEN_SIZE,
            "intermediate_size": INTERMEDIATE_SIZE,
            "local_experts": LOCAL_EXPERTS,
            "global_experts": GLOBAL_EXPERTS,
            "moe_layers": MOE_LAYERS,
        },
        "timing": {
            "warmup": args.warmup,
            "iterations_per_sample": args.iterations,
            "samples": args.samples,
            "routes": results,
        },
        "integration_gate": {
            "projection_basis": "3_local_typical_hash_critical_rank",
            "requires_projected_ms_per_token_at_least": 0.50,
            "projected_ms_per_token": typical_projection,
            "passed": typical_projection >= 0.50,
            "interpretation": (
                "GEMM2+gather minus GEMM2 is the graph-replay saving from "
                "deleting the complete gather node while retaining GEMM2. "
                "An epilogue fusion can additionally avoid about 96 KiB of "
                "BF16 intermediate traffic per layer, which is negligible "
                "relative to MXFP4 weight reads."
            ),
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))
    gemm_graph.reset()
    combined_graph.reset()
    gather_graph.reset()
    torch.xpu.synchronize()
    return 0 if payload["integration_gate"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
