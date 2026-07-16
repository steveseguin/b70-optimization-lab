#!/usr/bin/env python3
"""Gate a route-compact M=2 Xe2 MXFP4 scheduler on both routed GEMMs."""

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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ep-rank", type=int, choices=range(4), required=True)
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--warmup", type=int, default=30)
    parser.add_argument("--samples", type=int, default=9)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--required-ms", type=float, default=0.50)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    # The production control is N64. Fail closed against inherited shell state
    # so this remains a scheduler comparison rather than a hidden tile bakeoff.
    os.environ["VLLM_XPU_MXFP4_SMALL_M_N"] = "64"

    torch.manual_seed(20260716 + args.ep_rank)
    torch.xpu.manual_seed_all(20260716 + args.ep_rank)
    device = torch.device("xpu:0")
    local_experts = 40
    global_experts = 160
    topk = 6
    local_base = args.ep_rank * local_experts
    expert_map = torch.full(
        (global_experts,), -1, device=device, dtype=torch.int32
    )
    expert_map[local_base : local_base + local_experts] = torch.arange(
        local_experts, device=device, dtype=torch.int32
    )

    remote = [
        rank * local_experts for rank in range(4) if rank != args.ep_rank
    ]
    lb = local_base
    route_patterns = {
        "same_typical": [
            [lb, lb + 1, lb + 2, remote[0], remote[1], remote[2]],
            [lb, lb + 1, lb + 2, remote[0], remote[1], remote[2]],
        ],
        "disjoint_typical": [
            [lb, lb + 1, lb + 2, remote[0], remote[1], remote[2]],
            [
                lb + 3,
                lb + 4,
                lb + 5,
                remote[0] + 1,
                remote[1] + 1,
                remote[2] + 1,
            ],
        ],
        "cross_row_overlap": [
            [lb, lb + 1, lb + 2, remote[0], remote[1], remote[2]],
            [
                lb + 1,
                lb + 2,
                lb + 3,
                remote[0] + 1,
                remote[1] + 1,
                remote[2] + 1,
            ],
        ],
        "within_row_duplicate": [
            [lb, lb, lb + 1, remote[0], remote[1], remote[2]],
            [
                lb + 1,
                lb + 2,
                lb + 3,
                remote[0] + 1,
                remote[1] + 1,
                remote[2] + 1,
            ],
        ],
        "all_duplicate": [[lb] * 6, [lb] * 6],
        "six_local": [
            [lb + index for index in range(6)],
            [lb + index for index in range(6, 12)],
        ],
        "all_remote": [
            [
                remote[0],
                remote[1],
                remote[2],
                remote[0] + 1,
                remote[1] + 1,
                remote[2] + 1,
            ],
            [
                remote[0] + 2,
                remote[1] + 2,
                remote[2] + 2,
                remote[0] + 3,
                remote[1] + 3,
                remote[2] + 3,
            ],
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
    source1 = torch.randn((2, k1), device=device, dtype=torch.bfloat16) / 16
    activation1 = torch.empty((12, k1), device=device, dtype=torch.bfloat16)
    activation2 = torch.randn((12, k2), device=device, dtype=torch.bfloat16) / 16
    reference1 = torch.zeros((12, n), device=device, dtype=torch.bfloat16)
    reference2 = torch.zeros((12, n), device=device, dtype=torch.bfloat16)
    candidate1 = torch.zeros_like(reference1)
    candidate2 = torch.zeros_like(reference2)
    direct1 = torch.zeros_like(reference1)
    direct2 = torch.zeros_like(reference2)
    slot_activation2 = torch.zeros_like(activation2)
    topk_weights = torch.tensor(
        [
            [0.405, 0.325, 0.275, 0.205, 0.145, 0.115],
            [0.465, 0.345, 0.255, 0.195, 0.135, 0.105],
        ],
        device=device,
        dtype=torch.float32,
    )
    reference_gather = torch.zeros((2, n), device=device, dtype=torch.bfloat16)
    candidate_gather = torch.zeros_like(reference_gather)
    direct_gather = torch.zeros_like(reference_gather)
    rows_per_expert = torch.zeros(
        (local_experts,), device=device, dtype=torch.int32
    )
    topk_ids = torch.empty((2, topk), device=device, dtype=torch.int32)
    unpermuted = torch.empty((2, topk), device=device, dtype=torch.int32)

    def set_routes(pattern: list[list[int]]) -> int:
        flat = [expert for row in pattern for expert in row]
        counts = [0] * local_experts
        for global_expert in flat:
            local = global_expert - local_base
            if 0 <= local < local_experts:
                counts[local] += 1
        topk_ids.copy_(torch.tensor(pattern, device=device, dtype=torch.int32))
        return sum(counts)

    def refresh_remap() -> None:
        rows_per_expert.zero_()
        torch.ops._moe_C.remap_hidden_states(
            source1,
            None,
            activation1,
            None,
            expert_map,
            rows_per_expert,
            unpermuted,
            topk_ids,
            global_experts,
            local_experts,
        )

    def generic_call() -> None:
        torch.ops._xpu_C.cutlass_grouped_gemm_interface(
            activation1,
            None,
            weight1,
            scale1,
            None,
            reference1,
            rows_per_expert,
            n,
            k1,
            local_experts,
        )
        torch.ops._xpu_C.cutlass_grouped_gemm_interface(
            activation2,
            None,
            weight2,
            scale2,
            None,
            reference2,
            rows_per_expert,
            n,
            k2,
            local_experts,
        )

    def compact_call() -> None:
        torch.ops._xpu_C.cutlass_grouped_gemm_m2_compact_interface(
            activation1,
            weight1,
            scale1,
            None,
            candidate1,
            topk_ids,
            expert_map,
            n,
            k1,
            local_experts,
        )
        torch.ops._xpu_C.cutlass_grouped_gemm_m2_compact_interface(
            activation2,
            weight2,
            scale2,
            None,
            candidate2,
            topk_ids,
            expert_map,
            n,
            k2,
            local_experts,
        )

    def direct_oracle_call() -> list[list[int]]:
        # This is deliberately outside timing. The already-qualified fixed-M1
        # scheduler provides an independent per-route arithmetic oracle, while
        # the real remap metadata checks token/route association through gather.
        torch.xpu.synchronize()
        mapping = unpermuted.cpu().tolist()
        direct1.zero_()
        direct2.zero_()
        slot_activation2.zero_()
        for row in range(2):
            for slot in range(topk):
                mapped = mapping[row][slot]
                if mapped >= 0:
                    slot_activation2[row * topk + slot].copy_(
                        activation2[mapped]
                    )
            route_slice = topk_ids[row : row + 1]
            slot_slice = slice(row * topk, (row + 1) * topk)
            torch.ops._xpu_C.cutlass_grouped_gemm_m1_topk_interface(
                source1[row : row + 1],
                weight1,
                scale1,
                None,
                direct1[slot_slice],
                route_slice,
                expert_map,
                n,
                k1,
                local_experts,
                True,
            )
            torch.ops._xpu_C.cutlass_grouped_gemm_m1_topk_interface(
                slot_activation2[slot_slice],
                weight2,
                scale2,
                None,
                direct2[slot_slice],
                route_slice,
                expert_map,
                n,
                k2,
                local_experts,
                False,
            )

        torch.ops._moe_C.moe_gather(
            reference_gather,
            reference2,
            topk_weights,
            unpermuted,
            local_experts,
        )
        torch.ops._moe_C.moe_gather(
            candidate_gather,
            candidate2,
            topk_weights,
            unpermuted,
            local_experts,
        )
        for row in range(2):
            slot_slice = slice(row * topk, (row + 1) * topk)
            torch.ops._moe_C.moe_gather_direct_m1(
                direct_gather[row : row + 1],
                direct2[slot_slice],
                topk_weights[row : row + 1],
                topk_ids[row : row + 1],
                expert_map,
                local_experts,
            )
        torch.xpu.synchronize()
        return mapping

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

    set_routes(route_patterns["disjoint_typical"])
    refresh_remap()
    reference_graph = capture(generic_call)
    candidate_graph = capture(compact_call)

    correctness = []
    for pattern_index, (pattern_name, pattern) in enumerate(
        route_patterns.items()
    ):
        active_rows = set_routes(pattern)
        for epoch in range(args.epochs):
            generator = torch.Generator(device=device).manual_seed(
                20260716
                + args.ep_rank * 1000
                + pattern_index * 100
                + epoch
            )
            source1.copy_(
                torch.randn(
                    source1.shape,
                    device=device,
                    dtype=source1.dtype,
                    generator=generator,
                )
                / 16
            )
            activation2.copy_(
                torch.randn(
                    activation2.shape,
                    device=device,
                    dtype=activation2.dtype,
                    generator=generator,
                )
                / 16
            )
            refresh_remap()
            reference_graph.replay()
            candidate_graph.replay()
            torch.xpu.synchronize()
            mapping = direct_oracle_call()
            exact1 = torch.equal(
                reference1[:active_rows], candidate1[:active_rows]
            )
            exact2 = torch.equal(
                reference2[:active_rows], candidate2[:active_rows]
            )
            candidate_oracle1 = True
            candidate_oracle2 = True
            reference_oracle1 = True
            reference_oracle2 = True
            for row in range(2):
                for slot in range(topk):
                    mapped = mapping[row][slot]
                    if mapped < 0:
                        continue
                    flat_slot = row * topk + slot
                    candidate_oracle1 &= torch.equal(
                        candidate1[mapped], direct1[flat_slot]
                    )
                    candidate_oracle2 &= torch.equal(
                        candidate2[mapped], direct2[flat_slot]
                    )
                    reference_oracle1 &= torch.equal(
                        reference1[mapped], direct1[flat_slot]
                    )
                    reference_oracle2 &= torch.equal(
                        reference2[mapped], direct2[flat_slot]
                    )
            gather_exact = (
                torch.equal(reference_gather, candidate_gather)
                and torch.equal(candidate_gather, direct_gather)
            )
            oracle_exact = (
                candidate_oracle1
                and candidate_oracle2
                and reference_oracle1
                and reference_oracle2
                and gather_exact
            )
            correctness.append(
                {
                    "pattern": pattern_name,
                    "epoch": epoch,
                    "active_rows": active_rows,
                    "gemm1_exact": exact1,
                    "gemm2_exact": exact2,
                    "candidate_oracle_gemm1_exact": candidate_oracle1,
                    "candidate_oracle_gemm2_exact": candidate_oracle2,
                    "reference_oracle_gemm1_exact": reference_oracle1,
                    "reference_oracle_gemm2_exact": reference_oracle2,
                    "gather_exact": gather_exact,
                    "exact": exact1 and exact2 and oracle_exact,
                    "gemm1_mismatch_count": int(
                        torch.count_nonzero(
                            reference1[:active_rows]
                            != candidate1[:active_rows]
                        ).item()
                    ),
                    "gemm2_mismatch_count": int(
                        torch.count_nonzero(
                            reference2[:active_rows]
                            != candidate2[:active_rows]
                        ).item()
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

    timing_rows = []
    for pattern_name, pattern in route_patterns.items():
        set_routes(pattern)
        refresh_remap()
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
        saved_ms = (reference_us - candidate_us) * 43 / 1000.0
        timing_rows.append(
            {
                "route": pattern_name,
                "generic_two_gemm_median_us": reference_us,
                "compact_two_gemm_median_us": candidate_us,
                "speedup": reference_us / candidate_us,
                "saved_us_per_layer": reference_us - candidate_us,
                "projected_saved_ms_per_43_layers": saved_ms,
                "generic_samples_us": reference_samples,
                "compact_samples_us": candidate_samples,
            }
        )
    minimum_saved_ms = min(
        row["projected_saved_ms_per_43_layers"] for row in timing_rows
    )
    exact = all(row["exact"] for row in correctness)
    result = {
        "schema_version": 1,
        "classification": "deepseek_v4_mxfp4_m2_compact_scheduler_gate",
        "device": torch.xpu.get_device_name(device),
        "logical_device": str(device),
        "ep_rank": args.ep_rank,
        "generic_policy": "N64",
        "shape": {
            "m": 2,
            "gemm1": {"n": n, "k": k1},
            "gemm2": {"n": n, "k": k2},
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
            "selection_rule": "minimum savings across every declared route pattern",
            "rows": timing_rows,
            "minimum_projected_saved_ms_per_43_layers": minimum_saved_ms,
            "required_ms": args.required_ms,
            "clears_integration_gate": minimum_saved_ms >= args.required_ms,
        },
        "passed": exact and minimum_saved_ms >= args.required_ms,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {key: value for key, value in result.items() if key != "correctness"},
            indent=2,
        )
    )
    reference_graph.reset()
    candidate_graph.reset()
    torch.xpu.synchronize()
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
