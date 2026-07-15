#!/usr/bin/env python3
"""Gate the exact slot-direct M=1 MXFP4 routed-MoE candidate on one B70."""

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
MOE_LAYERS = 43


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * fraction)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--warmup", type=int, default=40)
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--samples", type=int, default=9)
    parser.add_argument("--seed", type=int, default=1729)
    parser.add_argument("--ep-rank", type=int, choices=range(4), default=0)
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

    hidden = torch.empty((1, HIDDEN_SIZE), dtype=torch.bfloat16, device=device)
    topk_ids = torch.empty((1, TOPK), dtype=torch.int32, device=device)
    topk_weights = torch.empty((1, TOPK), dtype=torch.float32, device=device)
    expert_map = torch.empty((GLOBAL_EXPERTS,), dtype=torch.int32, device=device)
    torch.ops._moe_C.init_expert_map(expert_map, LOCAL_EXPERTS, args.ep_rank, 4)
    local_base = args.ep_rank * LOCAL_EXPERTS
    remote_bases = [rank * LOCAL_EXPERTS for rank in range(4) if rank != args.ep_rank]

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

    remapped = torch.empty((TOPK, HIDDEN_SIZE), dtype=torch.bfloat16, device=device)
    rows_per_expert = torch.empty((LOCAL_EXPERTS,), dtype=torch.int32, device=device)
    unpermuted = torch.empty((1, TOPK), dtype=torch.int32, device=device)
    ref_gemm1 = torch.empty(
        (TOPK, 2 * INTERMEDIATE_SIZE), dtype=torch.bfloat16, device=device
    )
    ref_act = torch.empty((TOPK, INTERMEDIATE_SIZE), dtype=torch.bfloat16, device=device)
    ref_gemm2 = torch.empty((TOPK, HIDDEN_SIZE), dtype=torch.bfloat16, device=device)
    ref_output = torch.empty((1, HIDDEN_SIZE), dtype=torch.bfloat16, device=device)

    direct_gemm1 = torch.full(
        (TOPK, 2 * INTERMEDIATE_SIZE),
        float("nan"),
        dtype=torch.bfloat16,
        device=device,
    )
    direct_act = torch.empty(
        (TOPK, INTERMEDIATE_SIZE), dtype=torch.bfloat16, device=device
    )
    direct_gemm2 = torch.full(
        (TOPK, HIDDEN_SIZE), float("nan"), dtype=torch.bfloat16, device=device
    )
    direct_output = torch.empty((1, HIDDEN_SIZE), dtype=torch.bfloat16, device=device)

    def reference() -> None:
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
        torch.ops._xpu_C.cutlass_grouped_gemm_interface(
            remapped,
            None,
            w13,
            w13_scales,
            None,
            ref_gemm1,
            rows_per_expert,
            2 * INTERMEDIATE_SIZE,
            HIDDEN_SIZE,
            LOCAL_EXPERTS,
        )
        ref_gemm1[:, :INTERMEDIATE_SIZE].clamp_(max=10.0)
        ref_gemm1[:, INTERMEDIATE_SIZE:].clamp_(min=-10.0, max=10.0)
        torch.ops._C.silu_and_mul(ref_act, ref_gemm1)
        torch.ops._xpu_C.cutlass_grouped_gemm_interface(
            ref_act,
            None,
            w2,
            w2_scales,
            None,
            ref_gemm2,
            rows_per_expert,
            HIDDEN_SIZE,
            INTERMEDIATE_SIZE,
            LOCAL_EXPERTS,
        )
        torch.ops._moe_C.moe_gather(
            ref_output, ref_gemm2, topk_weights, unpermuted, LOCAL_EXPERTS
        )

    def candidate() -> None:
        torch.ops._xpu_C.cutlass_grouped_gemm_m1_topk_interface(
            hidden,
            w13,
            w13_scales,
            None,
            direct_gemm1,
            topk_ids,
            expert_map,
            2 * INTERMEDIATE_SIZE,
            HIDDEN_SIZE,
            LOCAL_EXPERTS,
            True,
        )
        torch.ops._C.silu_and_mul_clamp(direct_act, direct_gemm1, 10.0)
        torch.ops._xpu_C.cutlass_grouped_gemm_m1_topk_interface(
            direct_act,
            w2,
            w2_scales,
            None,
            direct_gemm2,
            topk_ids,
            expert_map,
            HIDDEN_SIZE,
            INTERMEDIATE_SIZE,
            LOCAL_EXPERTS,
            False,
        )
        torch.ops._moe_C.moe_gather_direct_m1(
            direct_output,
            direct_gemm2,
            topk_weights,
            topk_ids,
            expert_map,
            LOCAL_EXPERTS,
        )

    initial_ids = torch.tensor(
        [[local_base, remote_bases[0], remote_bases[1], remote_bases[2], local_base + 1, remote_bases[0] + 1]],
        dtype=torch.int32,
        device=device,
    )
    initial_weights = torch.tensor(
        [[0.465, 0.345, 0.255, 0.195, 0.135, 0.105]],
        dtype=torch.float32,
        device=device,
    )
    hidden.normal_(mean=0.0, std=1.0)
    topk_ids.copy_(initial_ids)
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
    reference_graph.replay()
    candidate_graph.replay()
    torch.xpu.synchronize()

    route_patterns = (
        [local_base + offset for offset in range(6)],
        [local_base, remote_bases[0], remote_bases[1], remote_bases[2], local_base + 1, remote_bases[0] + 1],
        [0, 40, 80, 120, 1, 41],
        [120, 80, 40, 0, 39, 159],
        [remote_bases[0], remote_bases[0] + 1, remote_bases[1], remote_bases[1] + 1, remote_bases[2], remote_bases[2] + 1],
        [local_base, local_base, local_base + 1, local_base + 1, remote_bases[0], remote_bases[0]],
        [120, 120, 39, 39, 159, 159],
    )
    exact_rows = []
    for epoch in range(args.epochs):
        generator = torch.Generator(device=device).manual_seed(args.seed + 37 * epoch)
        hidden.copy_(
            torch.randn(
                (1, HIDDEN_SIZE),
                dtype=torch.bfloat16,
                device=device,
                generator=generator,
            )
        )
        topk_ids.copy_(
            torch.tensor(
                [route_patterns[epoch % len(route_patterns)]],
                dtype=torch.int32,
                device=device,
            )
        )
        if epoch % 7 == 0:
            topk_weights.zero_()
        else:
            raw_weights = torch.rand((1, TOPK), dtype=torch.float32, device=device)
            topk_weights.copy_(
                1.5 * raw_weights / raw_weights.sum(dim=-1, keepdim=True)
            )
        reference_graph.replay()
        torch.xpu.synchronize()
        expected = ref_output.clone()
        expected_gemm1 = ref_gemm1.clone()
        expected_act = ref_act.clone()
        expected_gemm2 = ref_gemm2.clone()
        expected_unpermuted = unpermuted.cpu()
        candidate_graph.replay()
        torch.xpu.synchronize()
        candidate_clamped = direct_gemm1.clone()
        candidate_clamped[:, :INTERMEDIATE_SIZE].clamp_(max=10.0)
        candidate_clamped[:, INTERMEDIATE_SIZE:].clamp_(min=-10.0, max=10.0)
        torch.xpu.synchronize()
        route = route_patterns[epoch % len(route_patterns)]
        local_slot_rows = [
            (slot, int(expected_unpermuted[0, slot].item()))
            for slot, expert in enumerate(route)
            if local_base <= expert < local_base + LOCAL_EXPERTS
        ]
        gemm1_exact = all(
            torch.equal(expected_gemm1[row], candidate_clamped[slot])
            for slot, row in local_slot_rows
        )
        activation_exact = all(
            torch.equal(expected_act[row], direct_act[slot])
            for slot, row in local_slot_rows
        )
        gemm2_exact = all(
            torch.equal(expected_gemm2[row], direct_gemm2[slot])
            for slot, row in local_slot_rows
        )
        final_exact = torch.equal(expected, direct_output)
        candidate_repeat = direct_output.clone()
        candidate_graph.replay()
        reference_graph.replay()
        torch.xpu.synchronize()
        candidate_repeat_exact = torch.equal(candidate_repeat, direct_output)
        reference_repeat_exact = torch.equal(expected, ref_output)
        exact = (
            gemm1_exact
            and activation_exact
            and gemm2_exact
            and final_exact
            and candidate_repeat_exact
            and reference_repeat_exact
        )
        diff = (expected.float() - direct_output.float()).abs()
        exact_rows.append(
            {
                "epoch": epoch,
                "route": list(route_patterns[epoch % len(route_patterns)]),
                "exact": exact,
                "gemm1_local_slots_exact": gemm1_exact,
                "activation_local_slots_exact": activation_exact,
                "gemm2_local_slots_exact": gemm2_exact,
                "final_exact": final_exact,
                "candidate_a_b_a_exact": candidate_repeat_exact,
                "reference_a_b_a_exact": reference_repeat_exact,
                "mismatch_count": int((expected != direct_output).sum().item()),
                "max_abs_diff": float(diff.max().item()),
            }
        )

    def time_graph(graph: torch.xpu.XPUGraph) -> float:
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(args.iterations):
            graph.replay()
        end.record()
        end.synchronize()
        return start.elapsed_time(end) * 1000.0 / args.iterations

    timing_routes = {
        "2_local": [local_base, local_base + 1, remote_bases[0], remote_bases[1], remote_bases[2], remote_bases[0] + 1],
        "3_local": [local_base, local_base + 1, local_base + 2, remote_bases[0], remote_bases[1], remote_bases[2]],
        "4_local": [local_base, local_base + 1, local_base + 2, local_base + 3, remote_bases[0], remote_bases[1]],
        "6_local": [local_base + offset for offset in range(6)],
    }
    timing = {}
    for route_name, route in timing_routes.items():
        topk_ids.copy_(torch.tensor([route], dtype=torch.int32, device=device))
        topk_weights.copy_(initial_weights)
        for _ in range(args.warmup):
            reference_graph.replay()
            candidate_graph.replay()
        torch.xpu.synchronize()
        reference_samples = []
        candidate_samples = []
        for sample in range(args.samples):
            if sample % 2 == 0:
                reference_samples.append(time_graph(reference_graph))
                candidate_samples.append(time_graph(candidate_graph))
            else:
                candidate_samples.append(time_graph(candidate_graph))
                reference_samples.append(time_graph(reference_graph))
        reference_median = statistics.median(reference_samples)
        candidate_median = statistics.median(candidate_samples)
        saved_us = reference_median - candidate_median
        timing[route_name] = {
            "route": route,
            "reference_samples_us": reference_samples,
            "candidate_samples_us": candidate_samples,
            "reference_median_us": reference_median,
            "candidate_median_us": candidate_median,
            "saved_us_per_moe_layer": saved_us,
            "speedup": reference_median / candidate_median,
            "projected_ms_per_token": saved_us * MOE_LAYERS / 1000.0,
            "reference_p90_us": percentile(reference_samples, 0.90),
            "candidate_p90_us": percentile(candidate_samples, 0.90),
        }

    projected_ms_per_token = timing["3_local"]["projected_ms_per_token"]
    result = {
        "classification": "deepseek_v4_m1_direct_routed_moe_gate",
        "device": torch.xpu.get_device_name(),
        "torch": torch.__version__,
        "shape": {
            "hidden_size": HIDDEN_SIZE,
            "intermediate_size": INTERMEDIATE_SIZE,
            "local_experts": LOCAL_EXPERTS,
            "global_experts": GLOBAL_EXPERTS,
            "topk": TOPK,
            "moe_layers_per_token": MOE_LAYERS,
            "ep_rank": args.ep_rank,
        },
        "correctness": {
            "epochs": args.epochs,
            "exact_epochs": sum(row["exact"] for row in exact_rows),
            "passed": all(row["exact"] for row in exact_rows),
            "rows": exact_rows,
        },
        "timing": {
            "warmup": args.warmup,
            "iterations_per_sample": args.iterations,
            "samples": args.samples,
            "projection_basis": "3_local_typical_hash_critical_rank",
            "routes": timing,
        },
        "integration_gate": {
            "requires_exact": True,
            "requires_projected_ms_per_token_at_least": 0.50,
            "passed": all(row["exact"] for row in exact_rows)
            and projected_ms_per_token >= 0.50,
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "correctness"}, indent=2))
    print(json.dumps({"correctness": {k: v for k, v in result["correctness"].items() if k != "rows"}}, indent=2))

    reference_graph.reset()
    candidate_graph.reset()
    torch.xpu.synchronize()
    return 0 if result["integration_gate"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
