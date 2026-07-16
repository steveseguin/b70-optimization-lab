#!/usr/bin/env python3
"""Gate direct M=2 routed MoE using two exact direct-M=1 chains.

This intentionally adds no kernel.  It compares the production generic M=2
MXFP4 path with two calls to the already promoted slot-direct M=1 path.  A
merged M=2 kernel is worth implementing only if this conservative eight-node
upper bound is exact and saves at least 0.50 ms per 43-layer verifier cycle on
every declared route family.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
from pathlib import Path

import torch

import vllm_xpu_kernels._C  # noqa: F401
import vllm_xpu_kernels._moe_C  # noqa: F401
import vllm_xpu_kernels._xpu_C  # noqa: F401


HIDDEN_SIZE = 4096
INTERMEDIATE_SIZE = 2048
LOCAL_EXPERTS = 40
GLOBAL_EXPERTS = 160
TOPK = 6
ROWS = 2
MOE_LAYERS = 43


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--warmup", type=int, default=40)
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--samples", type=int, default=9)
    parser.add_argument("--seed", type=int, default=20260715)
    parser.add_argument("--ep-rank", type=int, choices=range(4), default=0)
    parser.add_argument("--required-ms", type=float, default=0.50)
    args = parser.parse_args()

    if os.environ.get("VLLM_XPU_MXFP4_SMALL_M_N") not in (None, "", "64"):
        raise RuntimeError("production timing requires MXFP4 N64/default policy")
    if os.environ.get("VLLM_XPU_FORCE_XE_DEFAULT_KERNEL", "0").lower() in (
        "1",
        "true",
    ):
        raise RuntimeError("direct Xe2 timing requires force-Xe-default disabled")

    torch.manual_seed(args.seed)
    torch.xpu.manual_seed_all(args.seed)
    device = torch.device("xpu:0")
    local_base = args.ep_rank * LOCAL_EXPERTS
    remote_bases = [rank * LOCAL_EXPERTS for rank in range(4) if rank != args.ep_rank]

    hidden = torch.empty((ROWS, HIDDEN_SIZE), dtype=torch.bfloat16, device=device)
    topk_ids = torch.empty((ROWS, TOPK), dtype=torch.int32, device=device)
    topk_weights = torch.empty((ROWS, TOPK), dtype=torch.float32, device=device)
    expert_map = torch.empty((GLOBAL_EXPERTS,), dtype=torch.int32, device=device)
    torch.ops._moe_C.init_expert_map(expert_map, LOCAL_EXPERTS, args.ep_rank, 4)

    w13 = torch.randint(
        0,
        256,
        (LOCAL_EXPERTS, 2 * INTERMEDIATE_SIZE, HIDDEN_SIZE // 2),
        dtype=torch.uint8,
        device=device,
    ).view(torch.float4_e2m1fn_x2)
    w13_scales = torch.randint(
        119,
        123,
        (LOCAL_EXPERTS, 2 * INTERMEDIATE_SIZE, HIDDEN_SIZE // 32),
        dtype=torch.uint8,
        device=device,
    )
    w2 = torch.randint(
        0,
        256,
        (LOCAL_EXPERTS, HIDDEN_SIZE, INTERMEDIATE_SIZE // 2),
        dtype=torch.uint8,
        device=device,
    ).view(torch.float4_e2m1fn_x2)
    w2_scales = torch.randint(
        119,
        123,
        (LOCAL_EXPERTS, HIDDEN_SIZE, INTERMEDIATE_SIZE // 32),
        dtype=torch.uint8,
        device=device,
    )

    total_slots = ROWS * TOPK
    remapped = torch.empty(
        (total_slots, HIDDEN_SIZE), dtype=torch.bfloat16, device=device
    )
    rows_per_expert = torch.empty((LOCAL_EXPERTS,), dtype=torch.int32, device=device)
    unpermuted = torch.empty((ROWS, TOPK), dtype=torch.int32, device=device)
    reference_gemm1 = torch.empty(
        (total_slots, 2 * INTERMEDIATE_SIZE), dtype=torch.bfloat16, device=device
    )
    reference_act = torch.empty(
        (total_slots, INTERMEDIATE_SIZE), dtype=torch.bfloat16, device=device
    )
    reference_gemm2 = torch.empty(
        (total_slots, HIDDEN_SIZE), dtype=torch.bfloat16, device=device
    )
    reference_output = torch.empty(
        (ROWS, HIDDEN_SIZE), dtype=torch.bfloat16, device=device
    )

    direct_gemm1 = [
        torch.empty(
            (TOPK, 2 * INTERMEDIATE_SIZE), dtype=torch.bfloat16, device=device
        )
        for _ in range(ROWS)
    ]
    direct_act = [
        torch.empty((TOPK, INTERMEDIATE_SIZE), dtype=torch.bfloat16, device=device)
        for _ in range(ROWS)
    ]
    direct_gemm2 = [
        torch.empty((TOPK, HIDDEN_SIZE), dtype=torch.bfloat16, device=device)
        for _ in range(ROWS)
    ]
    direct_output = [
        torch.empty((1, HIDDEN_SIZE), dtype=torch.bfloat16, device=device)
        for _ in range(ROWS)
    ]

    def stage_reference_inputs() -> None:
        rows_per_expert.zero_()
        torch.ops._moe_C.remap_hidden_states(
            hidden_states=hidden,
            hidden_states_scales=None,
            remapped_hidden_states=remapped,
            remapped_hidden_states_scales=None,
            expert_map=expert_map,
            rows_per_expert=rows_per_expert,
            unpermuted_row_to_permuted_row=unpermuted,
            topk_ids=topk_ids,
            total_experts_num=GLOBAL_EXPERTS,
            local_experts_num=LOCAL_EXPERTS,
        )

    def compute_reference_from_staged() -> None:
        torch.ops._xpu_C.cutlass_grouped_gemm_interface(
            remapped,
            None,
            w13,
            w13_scales,
            None,
            reference_gemm1,
            rows_per_expert,
            2 * INTERMEDIATE_SIZE,
            HIDDEN_SIZE,
            LOCAL_EXPERTS,
        )
        reference_gemm1[:, :INTERMEDIATE_SIZE].clamp_(max=10.0)
        reference_gemm1[:, INTERMEDIATE_SIZE:].clamp_(min=-10.0, max=10.0)
        torch.ops._C.silu_and_mul(reference_act, reference_gemm1)
        torch.ops._xpu_C.cutlass_grouped_gemm_interface(
            reference_act,
            None,
            w2,
            w2_scales,
            None,
            reference_gemm2,
            rows_per_expert,
            HIDDEN_SIZE,
            INTERMEDIATE_SIZE,
            LOCAL_EXPERTS,
        )
        torch.ops._moe_C.moe_gather(
            reference_output,
            reference_gemm2,
            topk_weights,
            unpermuted,
            LOCAL_EXPERTS,
        )

    def reference() -> None:
        stage_reference_inputs()
        compute_reference_from_staged()

    def candidate() -> None:
        for row in range(ROWS):
            torch.ops._xpu_C.cutlass_grouped_gemm_m1_topk_interface(
                hidden[row : row + 1],
                w13,
                w13_scales,
                None,
                direct_gemm1[row],
                topk_ids[row : row + 1],
                expert_map,
                2 * INTERMEDIATE_SIZE,
                HIDDEN_SIZE,
                LOCAL_EXPERTS,
                True,
            )
            torch.ops._C.silu_and_mul_clamp(
                direct_act[row], direct_gemm1[row], 10.0
            )
            torch.ops._xpu_C.cutlass_grouped_gemm_m1_topk_interface(
                direct_act[row],
                w2,
                w2_scales,
                None,
                direct_gemm2[row],
                topk_ids[row : row + 1],
                expert_map,
                HIDDEN_SIZE,
                INTERMEDIATE_SIZE,
                LOCAL_EXPERTS,
                False,
            )
            torch.ops._moe_C.moe_gather_direct_m1(
                direct_output[row],
                direct_gemm2[row],
                topk_weights[row : row + 1],
                topk_ids[row : row + 1],
                expert_map,
                LOCAL_EXPERTS,
            )

    lb = local_base
    rb = remote_bases
    route_families = {
        "same_typical": [
            [lb, lb + 1, lb + 2, rb[0], rb[1], rb[2]],
            [lb, lb + 1, lb + 2, rb[0], rb[1], rb[2]],
        ],
        "disjoint_typical": [
            [lb, lb + 1, lb + 2, rb[0], rb[1], rb[2]],
            [lb + 3, lb + 4, lb + 5, rb[0] + 1, rb[1] + 1, rb[2] + 1],
        ],
        "cross_row_overlap": [
            [lb, lb + 1, lb + 2, rb[0], rb[1], rb[2]],
            [lb + 1, lb + 2, lb + 3, rb[0] + 1, rb[1] + 1, rb[2] + 1],
        ],
        "within_row_duplicates": [
            [lb, lb, lb + 1, lb + 1, rb[0], rb[0]],
            [lb + 2, lb + 2, lb + 3, lb + 3, rb[1], rb[1]],
        ],
        "mixed_ep": [
            [0, 40, 80, 120, 1, 41],
            [120, 80, 40, 0, 39, 159],
        ],
    }
    initial_weights = torch.tensor(
        [
            [0.465, 0.345, 0.255, 0.195, 0.135, 0.105],
            [0.405, 0.325, 0.275, 0.205, 0.145, 0.115],
        ],
        dtype=torch.float32,
        device=device,
    )
    hidden.normal_(mean=0.0, std=1.0)
    topk_ids.copy_(torch.tensor(route_families["mixed_ep"], dtype=torch.int32, device=device))
    topk_weights.copy_(initial_weights)
    for _ in range(3):
        reference()
        candidate()
    torch.xpu.synchronize()

    reference_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(reference_graph):
        reference()
    candidate_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(candidate_graph):
        candidate()
    # This is an upper bound for eliminating route staging.  It keeps both
    # grouped GEMMs, activation, and gather unchanged, but consumes a route
    # layout prepared immediately before replay.
    stage_reference_inputs()
    compute_only_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(compute_only_graph):
        compute_reference_from_staged()
    reference_graph.replay()
    candidate_graph.replay()
    torch.xpu.synchronize()

    correctness_rows = []
    route_names = tuple(route_families)
    for epoch in range(args.epochs):
        generator = torch.Generator(device=device).manual_seed(args.seed + 37 * epoch)
        hidden.copy_(
            torch.randn(
                hidden.shape,
                dtype=hidden.dtype,
                device=device,
                generator=generator,
            )
            * (0.25 + 0.25 * (epoch % 8))
        )
        route_name = route_names[epoch % len(route_names)]
        topk_ids.copy_(
            torch.tensor(route_families[route_name], dtype=torch.int32, device=device)
        )
        if epoch % 11 == 0:
            topk_weights.zero_()
        else:
            raw = torch.rand((ROWS, TOPK), dtype=torch.float32, device=device)
            topk_weights.copy_(1.5 * raw / raw.sum(dim=-1, keepdim=True))
        reference_graph.replay()
        torch.xpu.synchronize()
        expected = reference_output.clone()
        candidate_graph.replay()
        torch.xpu.synchronize()
        actual = torch.cat(direct_output, dim=0)
        first = actual.clone()
        reference_graph.replay()
        candidate_graph.replay()
        torch.xpu.synchronize()
        actual_repeat = torch.cat(direct_output, dim=0)
        mismatches = int(torch.count_nonzero(expected != actual_repeat).item())
        correctness_rows.append(
            {
                "epoch": epoch,
                "route_family": route_name,
                "mismatches": mismatches,
                "max_abs_diff": float(
                    (expected.float() - actual_repeat.float()).abs().max().item()
                ),
                "candidate_repeat_exact": torch.equal(first, actual_repeat),
                "reference_repeat_exact": torch.equal(expected, reference_output),
            }
        )

    def timed_graph_us(graph: torch.xpu.XPUGraph) -> float:
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(args.iterations):
            graph.replay()
        end.record()
        end.synchronize()
        return start.elapsed_time(end) * 1000.0 / args.iterations

    timing = {}
    for route_name, route in route_families.items():
        topk_ids.copy_(torch.tensor(route, dtype=torch.int32, device=device))
        topk_weights.copy_(initial_weights)
        for _ in range(args.warmup):
            reference_graph.replay()
            candidate_graph.replay()
        torch.xpu.synchronize()
        reference_samples = []
        compute_only_samples = []
        candidate_samples = []
        for sample in range(args.samples):
            # Refresh the staged route before timing its compute-only graph.
            stage_reference_inputs()
            torch.xpu.synchronize()
            if sample % 2 == 0:
                reference_samples.append(timed_graph_us(reference_graph))
                compute_only_samples.append(timed_graph_us(compute_only_graph))
                candidate_samples.append(timed_graph_us(candidate_graph))
            else:
                candidate_samples.append(timed_graph_us(candidate_graph))
                compute_only_samples.append(timed_graph_us(compute_only_graph))
                reference_samples.append(timed_graph_us(reference_graph))
        reference_median = statistics.median(reference_samples)
        compute_only_median = statistics.median(compute_only_samples)
        candidate_median = statistics.median(candidate_samples)
        saved_us = reference_median - candidate_median
        stage_upper_bound_us = reference_median - compute_only_median
        timing[route_name] = {
            "route": route,
            "reference_samples_us": reference_samples,
            "compute_only_samples_us": compute_only_samples,
            "candidate_samples_us": candidate_samples,
            "reference_median_us": reference_median,
            "compute_only_median_us": compute_only_median,
            "candidate_median_us": candidate_median,
            "saved_us_per_layer": saved_us,
            "projected_saved_ms_per_cycle": saved_us * MOE_LAYERS / 1000.0,
            "speedup": reference_median / candidate_median,
            "route_staging_upper_bound_us_per_layer": stage_upper_bound_us,
            "route_staging_upper_bound_ms_per_cycle": (
                stage_upper_bound_us * MOE_LAYERS / 1000.0
            ),
        }

    exact = all(
        row["mismatches"] == 0
        and row["candidate_repeat_exact"]
        and row["reference_repeat_exact"]
        for row in correctness_rows
    )
    minimum_projected_ms = min(
        row["projected_saved_ms_per_cycle"] for row in timing.values()
    )
    minimum_staging_upper_bound_ms = min(
        row["route_staging_upper_bound_ms_per_cycle"] for row in timing.values()
    )
    result = {
        "schema_version": 1,
        "classification": "deepseek_v4_m2_direct_routed_moe_upper_bound_gate",
        "device": torch.xpu.get_device_name(device),
        "torch_version": torch.__version__,
        "shape": {
            "rows": ROWS,
            "hidden_size": HIDDEN_SIZE,
            "intermediate_size": INTERMEDIATE_SIZE,
            "local_experts": LOCAL_EXPERTS,
            "global_experts": GLOBAL_EXPERTS,
            "topk": TOPK,
            "moe_layers_per_verification": MOE_LAYERS,
            "ep_rank": args.ep_rank,
        },
        "correctness": {
            "exact": exact,
            "epochs": args.epochs,
            "rows": correctness_rows,
        },
        "timing": {
            "warmup": args.warmup,
            "iterations_per_sample": args.iterations,
            "samples": args.samples,
            "routes": timing,
            "minimum_projected_saved_ms_per_cycle": minimum_projected_ms,
            "minimum_route_staging_upper_bound_ms_per_cycle": (
                minimum_staging_upper_bound_ms
            ),
        },
        "gate": {
            "requires_all_route_families": True,
            "required_projected_ms": args.required_ms,
            "passed": exact and minimum_projected_ms >= args.required_ms,
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "classification": result["classification"],
                "device": result["device"],
                "correctness_exact": exact,
                "timing": timing,
                "gate": result["gate"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    reference_graph.reset()
    candidate_graph.reset()
    compute_only_graph.reset()
    torch.xpu.synchronize()
    return 0 if result["gate"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
