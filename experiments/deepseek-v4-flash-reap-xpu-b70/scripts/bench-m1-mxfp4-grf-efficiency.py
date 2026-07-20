#!/usr/bin/env python3
"""Four-card-ready exact/timing gate for the M=1 N64 MXFP4 GRF screen."""

from __future__ import annotations

import argparse
import json
import os
import statistics
from pathlib import Path

import torch

import vllm_xpu_kernels._C  # noqa: F401
import vllm_xpu_kernels._moe_C  # noqa: F401


HIDDEN = 4096
INTERMEDIATE = 2048
LOCAL_EXPERTS = 40
GLOBAL_EXPERTS = 160
TOPK = 6
MOE_LAYERS = 43
SELECTOR = "VLLM_XPU_MXFP4_M1_GRF128"


def set_candidate(enabled: bool) -> None:
    os.environ[SELECTOR] = "1" if enabled else "0"


def timed_us(call, iterations: int) -> float:
    start = torch.xpu.Event(enable_timing=True)
    end = torch.xpu.Event(enable_timing=True)
    start.record()
    for _ in range(iterations):
        call()
    end.record()
    end.synchronize()
    return start.elapsed_time(end) * 1000.0 / iterations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xpu-library", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--ep-rank", type=int, choices=range(4), required=True)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--warmups", type=int, default=40)
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--samples", type=int, default=9)
    parser.add_argument("--seed", type=int, default=20260720)
    args = parser.parse_args()

    if os.environ.get("VLLM_XPU_MXFP4_SMALL_M_N", "64") not in ("", "64"):
        raise RuntimeError("this gate qualifies only the incumbent N64 policy")
    torch.ops.load_library(str(args.xpu_library.resolve()))
    torch.manual_seed(args.seed + args.ep_rank)
    torch.xpu.manual_seed_all(args.seed + args.ep_rank)
    device = torch.device("xpu:0")

    hidden = torch.empty((1, HIDDEN), dtype=torch.bfloat16, device=device)
    topk_ids = torch.empty((1, TOPK), dtype=torch.int32, device=device)
    topk_weights = torch.empty((1, TOPK), dtype=torch.float32, device=device)
    expert_map = torch.empty((GLOBAL_EXPERTS,), dtype=torch.int32, device=device)
    torch.ops._moe_C.init_expert_map(
        expert_map, LOCAL_EXPERTS, args.ep_rank, 4
    )
    local_base = args.ep_rank * LOCAL_EXPERTS
    remote_bases = [
        rank * LOCAL_EXPERTS for rank in range(4) if rank != args.ep_rank
    ]

    w13 = torch.randint(
        0,
        256,
        (LOCAL_EXPERTS, 2 * INTERMEDIATE, HIDDEN // 2),
        dtype=torch.uint8,
        device=device,
    ).view(torch.float4_e2m1fn_x2)
    w13_scales = torch.randint(
        119,
        123,
        (LOCAL_EXPERTS, 2 * INTERMEDIATE, HIDDEN // 32),
        dtype=torch.uint8,
        device=device,
    )
    w2 = torch.randint(
        0,
        256,
        (LOCAL_EXPERTS, HIDDEN, INTERMEDIATE // 2),
        dtype=torch.uint8,
        device=device,
    ).view(torch.float4_e2m1fn_x2)
    w2_scales = torch.randint(
        119,
        123,
        (LOCAL_EXPERTS, HIDDEN, INTERMEDIATE // 32),
        dtype=torch.uint8,
        device=device,
    )

    def make_buffers() -> tuple[torch.Tensor, ...]:
        return (
            torch.full(
                (TOPK, 2 * INTERMEDIATE),
                float("nan"),
                dtype=torch.bfloat16,
                device=device,
            ),
            torch.empty(
                (TOPK, INTERMEDIATE), dtype=torch.bfloat16, device=device
            ),
            torch.full(
                (TOPK, HIDDEN),
                float("nan"),
                dtype=torch.bfloat16,
                device=device,
            ),
            torch.empty((1, HIDDEN), dtype=torch.bfloat16, device=device),
        )

    baseline = make_buffers()
    candidate = make_buffers()

    def run(buffers: tuple[torch.Tensor, ...]) -> None:
        gemm1, act, gemm2, output = buffers
        torch.ops._xpu_C.cutlass_grouped_gemm_m1_topk_interface(
            hidden,
            w13,
            w13_scales,
            None,
            gemm1,
            topk_ids,
            expert_map,
            2 * INTERMEDIATE,
            HIDDEN,
            LOCAL_EXPERTS,
            True,
        )
        torch.ops._C.silu_and_mul_clamp(act, gemm1, 10.0)
        torch.ops._xpu_C.cutlass_grouped_gemm_m1_topk_interface(
            act,
            w2,
            w2_scales,
            None,
            gemm2,
            topk_ids,
            expert_map,
            HIDDEN,
            INTERMEDIATE,
            LOCAL_EXPERTS,
            False,
        )
        torch.ops._moe_C.moe_gather_direct_m1(
            output,
            gemm2,
            topk_weights,
            topk_ids,
            expert_map,
            LOCAL_EXPERTS,
        )

    def compare(
        expected: tuple[torch.Tensor, ...],
        actual: tuple[torch.Tensor, ...],
        route: list[int],
    ) -> dict[str, int | bool | float]:
        local_slots = [
            slot
            for slot, expert in enumerate(route)
            if local_base <= expert < local_base + LOCAL_EXPERTS
        ]
        names = ("gemm1", "activation", "gemm2")
        mismatches: dict[str, int] = {}
        for name, left, right in zip(names, expected[:3], actual[:3], strict=True):
            if local_slots:
                mismatches[name] = int(
                    (left[local_slots] != right[local_slots]).sum().item()
                )
            else:
                mismatches[name] = 0
        mismatches["final"] = int((expected[3] != actual[3]).sum().item())
        max_abs = float(
            (expected[3].float() - actual[3].float()).abs().max().item()
        )
        return {
            "exact": not any(mismatches.values()),
            "local_slots": len(local_slots),
            "mismatch_count": sum(mismatches.values()),
            "max_abs_diff": max_abs,
            **{f"{name}_mismatches": value for name, value in mismatches.items()},
        }

    routes = (
        [local_base + offset for offset in range(6)],
        [
            local_base,
            remote_bases[0],
            remote_bases[1],
            remote_bases[2],
            local_base + 1,
            remote_bases[0] + 1,
        ],
        [0, 40, 80, 120, 1, 41],
        [120, 80, 40, 0, 39, 159],
        [
            remote_bases[0],
            remote_bases[0] + 1,
            remote_bases[1],
            remote_bases[1] + 1,
            remote_bases[2],
            remote_bases[2] + 1,
        ],
        [
            local_base,
            local_base,
            local_base + 1,
            local_base + 1,
            remote_bases[0],
            remote_bases[0],
        ],
    )

    eager_rows = []
    for epoch in range(args.epochs):
        generator = torch.Generator(device=device).manual_seed(
            args.seed + args.ep_rank * 1009 + epoch * 37
        )
        hidden.copy_(
            torch.randn(
                (1, HIDDEN),
                dtype=torch.bfloat16,
                device=device,
                generator=generator,
            )
        )
        route = routes[epoch % len(routes)]
        topk_ids.copy_(torch.tensor([route], dtype=torch.int32, device=device))
        weights = torch.rand(
            (1, TOPK), dtype=torch.float32, device=device, generator=generator
        )
        topk_weights.copy_(weights / weights.sum(dim=-1, keepdim=True))
        set_candidate(False)
        run(baseline)
        torch.xpu.synchronize()
        expected = tuple(value.clone() for value in baseline)
        set_candidate(True)
        run(candidate)
        torch.xpu.synchronize()
        row = compare(expected, candidate, route)
        set_candidate(False)
        run(baseline)
        torch.xpu.synchronize()
        repeat = compare(expected, baseline, route)
        row.update(
            epoch=epoch,
            route=route,
            baseline_a_b_a_exact=repeat["exact"],
            exact=bool(row["exact"] and repeat["exact"]),
        )
        eager_rows.append(row)

    set_candidate(False)
    baseline_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(baseline_graph):
        run(baseline)
    set_candidate(True)
    candidate_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(candidate_graph):
        run(candidate)

    graph_rows = []
    for epoch in range(args.epochs):
        generator = torch.Generator(device=device).manual_seed(
            args.seed + 100000 + args.ep_rank * 1009 + epoch * 41
        )
        hidden.copy_(
            torch.randn(
                (1, HIDDEN),
                dtype=torch.bfloat16,
                device=device,
                generator=generator,
            )
        )
        route = routes[(epoch + 1) % len(routes)]
        topk_ids.copy_(torch.tensor([route], dtype=torch.int32, device=device))
        weights = torch.rand(
            (1, TOPK), dtype=torch.float32, device=device, generator=generator
        )
        topk_weights.copy_(weights / weights.sum(dim=-1, keepdim=True))
        baseline_graph.replay()
        torch.xpu.synchronize()
        expected = tuple(value.clone() for value in baseline)
        candidate_graph.replay()
        torch.xpu.synchronize()
        row = compare(expected, candidate, route)
        baseline_graph.replay()
        torch.xpu.synchronize()
        repeat = compare(expected, baseline, route)
        row.update(
            epoch=epoch,
            route=route,
            baseline_a_b_a_exact=repeat["exact"],
            exact=bool(row["exact"] and repeat["exact"]),
        )
        graph_rows.append(row)

    timing_routes = {
        "2_local": [
            local_base,
            local_base + 1,
            remote_bases[0],
            remote_bases[1],
            remote_bases[2],
            remote_bases[0] + 1,
        ],
        "3_local": [
            local_base,
            local_base + 1,
            local_base + 2,
            remote_bases[0],
            remote_bases[1],
            remote_bases[2],
        ],
        "4_local": [
            local_base,
            local_base + 1,
            local_base + 2,
            local_base + 3,
            remote_bases[0],
            remote_bases[1],
        ],
        "6_local": [local_base + offset for offset in range(6)],
    }
    timing = {}
    for name, route in timing_routes.items():
        topk_ids.copy_(torch.tensor([route], dtype=torch.int32, device=device))
        topk_weights.fill_(1.0 / TOPK)
        for _ in range(args.warmups):
            baseline_graph.replay()
            candidate_graph.replay()
        torch.xpu.synchronize()
        baseline_samples = []
        candidate_samples = []
        for sample in range(args.samples):
            if sample % 2:
                candidate_samples.append(
                    timed_us(candidate_graph.replay, args.iterations)
                )
                baseline_samples.append(
                    timed_us(baseline_graph.replay, args.iterations)
                )
            else:
                baseline_samples.append(
                    timed_us(baseline_graph.replay, args.iterations)
                )
                candidate_samples.append(
                    timed_us(candidate_graph.replay, args.iterations)
                )
        baseline_us = statistics.median(baseline_samples)
        candidate_us = statistics.median(candidate_samples)
        saved_us = baseline_us - candidate_us
        local_count = int(name.split("_", 1)[0])
        weight_bytes_per_local = (
            (2 * INTERMEDIATE * HIDDEN // 2)
            + (2 * INTERMEDIATE * HIDDEN // 32)
            + (HIDDEN * INTERMEDIATE // 2)
            + (HIDDEN * INTERMEDIATE // 32)
        )
        timing[name] = {
            "route": route,
            "logical_weight_bytes": weight_bytes_per_local * local_count,
            "baseline_samples_us": baseline_samples,
            "candidate_samples_us": candidate_samples,
            "baseline_median_us": baseline_us,
            "candidate_median_us": candidate_us,
            "saved_us_per_layer": saved_us,
            "projected_saved_ms_per_token": saved_us * MOE_LAYERS / 1000.0,
            "baseline_logical_weight_gb_s": (
                weight_bytes_per_local * local_count / baseline_us / 1000.0
            ),
            "candidate_logical_weight_gb_s": (
                weight_bytes_per_local * local_count / candidate_us / 1000.0
            ),
        }

    eager_passed = all(bool(row["exact"]) for row in eager_rows)
    graph_passed = all(bool(row["exact"]) for row in graph_rows)
    typical = timing["3_local"]
    result = {
        "classification": "deepseek_v4_m1_mxfp4_grf_efficiency_gate",
        "device": torch.xpu.get_device_name(),
        "torch": torch.__version__,
        "ep_rank": args.ep_rank,
        "selector": {SELECTOR: "0=GRF256 control, 1=GRF128 candidate"},
        "shape": {
            "hidden": HIDDEN,
            "intermediate": INTERMEDIATE,
            "topk": TOPK,
            "local_experts": LOCAL_EXPERTS,
            "moe_layers": MOE_LAYERS,
            "tile": "M8xN64xK32",
            "subgroup": 16,
        },
        "correctness": {
            "eager": {
                "epochs": len(eager_rows),
                "exact_epochs": sum(bool(row["exact"]) for row in eager_rows),
                "passed": eager_passed,
                "rows": eager_rows,
            },
            "fixed_address_graph": {
                "epochs": len(graph_rows),
                "exact_epochs": sum(bool(row["exact"]) for row in graph_rows),
                "passed": graph_passed,
                "rows": graph_rows,
            },
        },
        "timing": {
            "warmups": args.warmups,
            "iterations": args.iterations,
            "samples": args.samples,
            "routes": timing,
        },
        "gate": {
            "basis": "3_local route projected across 43 routed layers",
            "required_ms_per_token": 0.30,
            "measured_ms_per_token": typical["projected_saved_ms_per_token"],
            "passed": eager_passed
            and graph_passed
            and typical["projected_saved_ms_per_token"] >= 0.30,
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "ep_rank": args.ep_rank,
                "correctness": {
                    "eager": result["correctness"]["eager"]["passed"],
                    "graph": result["correctness"]["fixed_address_graph"][
                        "passed"
                    ],
                },
                "timing": timing,
                "gate": result["gate"],
            },
            indent=2,
        )
    )
    baseline_graph.reset()
    candidate_graph.reset()
    torch.xpu.synchronize()
    return 0 if eager_passed and graph_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
