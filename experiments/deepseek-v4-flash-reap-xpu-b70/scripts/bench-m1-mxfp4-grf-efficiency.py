#!/usr/bin/env python3
"""Four-card-ready exact/timing gate for M=1 N64 MXFP4 tuning."""

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


HIDDEN = 4096
INTERMEDIATE = 2048
LOCAL_EXPERTS = 40
GLOBAL_EXPERTS = 160
TOPK = 6
MOE_LAYERS = 43
SELECTOR = "VLLM_XPU_MXFP4_M1_PREFETCH_MODE"
TILE_SELECTOR = "VLLM_XPU_MXFP4_TILE_MAJOR_PREPACK"


def set_candidate(enabled: bool, mode: str) -> None:
    os.environ[SELECTOR] = mode if enabled and mode != "tile-major" else ""
    os.environ[TILE_SELECTOR] = (
        "1" if enabled and mode == "tile-major" else ""
    )


def tile_major_prepack(
    weight: torch.Tensor, scales: torch.Tensor
) -> tuple[torch.Tensor, torch.Tensor]:
    experts, n, packed_k = weight.shape
    groups = packed_k // 16
    weight_tiles = (
        weight.view(torch.uint8)
        .reshape(experts, n // 64, 64, groups, 16)
        .permute(0, 1, 3, 2, 4)
        .reshape(experts, n // 64, groups, 1024)
    )
    scale_tiles = (
        scales.view(torch.uint8)
        .reshape(experts, n // 64, 64, groups)
        .permute(0, 1, 3, 2)
        .reshape(experts, n // 64, groups, 64)
    )
    records = torch.cat((weight_tiles, scale_tiles), dim=-1).contiguous()
    combined = records.reshape(experts, n, groups * 17)
    return combined.view(torch.float4_e2m1fn_x2), combined


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
    parser.add_argument("--eager-epochs", type=int)
    parser.add_argument("--graph-epochs", type=int)
    parser.add_argument("--warmups", type=int, default=40)
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--samples", type=int, default=9)
    parser.add_argument("--seed", type=int, default=20260720)
    parser.add_argument(
        "--candidate-mode",
        choices=(
            "d2", "d3", "d4", "d2-noa", "d3-noa", "d4-noa",
            "tile-major",
        ),
        required=True,
    )
    args = parser.parse_args()
    eager_epochs = args.eager_epochs or args.epochs
    graph_epochs = args.graph_epochs or args.epochs

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
    w13_tile, w13_scales_tile = tile_major_prepack(w13, w13_scales)
    w2_tile, w2_scales_tile = tile_major_prepack(w2, w2_scales)

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

    def run(buffers: tuple[torch.Tensor, ...], packed: bool = False) -> None:
        gemm1, act, gemm2, output = buffers
        w13_arg = w13_tile if packed else w13
        w13_scales_arg = w13_scales_tile if packed else w13_scales
        w2_arg = w2_tile if packed else w2
        w2_scales_arg = w2_scales_tile if packed else w2_scales
        torch.ops._xpu_C.cutlass_grouped_gemm_m1_topk_interface(
            hidden,
            w13_arg,
            w13_scales_arg,
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
            w2_arg,
            w2_scales_arg,
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
                left_bits = left[local_slots].contiguous().view(torch.uint16)
                right_bits = right[local_slots].contiguous().view(torch.uint16)
                mismatches[name] = int((left_bits != right_bits).sum().item())
            else:
                mismatches[name] = 0
        mismatches["final"] = int(
            (
                expected[3].view(torch.uint16)
                != actual[3].view(torch.uint16)
            ).sum().item()
        )
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
    tile_candidate = args.candidate_mode == "tile-major"
    for epoch in range(eager_epochs):
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
        set_candidate(False, args.candidate_mode)
        run(baseline)
        torch.xpu.synchronize()
        expected = tuple(value.clone() for value in baseline)
        set_candidate(True, args.candidate_mode)
        run(candidate, tile_candidate)
        torch.xpu.synchronize()
        row = compare(expected, candidate, route)
        set_candidate(False, args.candidate_mode)
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

    set_candidate(False, args.candidate_mode)
    baseline_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(baseline_graph):
        run(baseline)
    set_candidate(True, args.candidate_mode)
    candidate_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(candidate_graph):
        run(candidate, tile_candidate)

    def run_gemm1(buffers: tuple[torch.Tensor, ...], packed: bool = False) -> None:
        torch.ops._xpu_C.cutlass_grouped_gemm_m1_topk_interface(
            hidden,
            w13_tile if packed else w13,
            w13_scales_tile if packed else w13_scales,
            None,
            buffers[0],
            topk_ids,
            expert_map,
            2 * INTERMEDIATE,
            HIDDEN,
            LOCAL_EXPERTS,
            True,
        )

    def run_gemm2(buffers: tuple[torch.Tensor, ...], packed: bool = False) -> None:
        torch.ops._xpu_C.cutlass_grouped_gemm_m1_topk_interface(
            buffers[1],
            w2_tile if packed else w2,
            w2_scales_tile if packed else w2_scales,
            None,
            buffers[2],
            topk_ids,
            expert_map,
            HIDDEN,
            INTERMEDIATE,
            LOCAL_EXPERTS,
            False,
        )

    set_candidate(False, args.candidate_mode)
    baseline_gemm1_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(baseline_gemm1_graph):
        run_gemm1(baseline)
    baseline_gemm2_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(baseline_gemm2_graph):
        run_gemm2(baseline)
    set_candidate(True, args.candidate_mode)
    candidate_gemm1_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(candidate_gemm1_graph):
        run_gemm1(candidate, tile_candidate)
    candidate_gemm2_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(candidate_gemm2_graph):
        run_gemm2(candidate, tile_candidate)

    def replay_baseline_gemms() -> None:
        baseline_gemm1_graph.replay()
        baseline_gemm2_graph.replay()

    def replay_candidate_gemms() -> None:
        candidate_gemm1_graph.replay()
        candidate_gemm2_graph.replay()

    graph_rows = []
    for epoch in range(graph_epochs):
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
            replay_baseline_gemms()
            replay_candidate_gemms()
        torch.xpu.synchronize()
        baseline_samples = []
        candidate_samples = []
        for sample in range(args.samples):
            if sample % 2:
                candidate_samples.append(
                    timed_us(replay_candidate_gemms, args.iterations)
                )
                baseline_samples.append(
                    timed_us(replay_baseline_gemms, args.iterations)
                )
            else:
                baseline_samples.append(
                    timed_us(replay_baseline_gemms, args.iterations)
                )
                candidate_samples.append(
                    timed_us(replay_candidate_gemms, args.iterations)
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
    worst_route_name, worst_route = min(
        timing.items(),
        key=lambda item: item[1]["projected_saved_ms_per_token"],
    )
    result = {
        "classification": (
            "deepseek_v4_m1_mxfp4_tile_prepack_efficiency_gate"
            if tile_candidate
            else "deepseek_v4_m1_mxfp4_prefetch_efficiency_gate"
        ),
        "device": torch.xpu.get_device_name(),
        "torch": torch.__version__,
        "ep_rank": args.ep_rank,
        "selector": {
            (TILE_SELECTOR if tile_candidate else SELECTOR):
            f"unset=incumbent layout, {args.candidate_mode}=candidate"
        },
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
                "required_positions": {
                    "28": bool(len(graph_rows) >= 28 and graph_rows[27]["exact"]),
                    "58": bool(len(graph_rows) >= 58 and graph_rows[57]["exact"]),
                },
            },
        },
        "timing": {
            "warmups": args.warmups,
            "iterations": args.iterations,
            "samples": args.samples,
            "routes": timing,
        },
        "gate": {
            "basis": (
                "minimum exact saving across valid 2/3/4/6-local routes, "
                "projected across 43 routed layers"
            ),
            "worst_route": worst_route_name,
            "required_ms_per_token": 0.50 if tile_candidate else 0.30,
            "measured_ms_per_token": worst_route[
                "projected_saved_ms_per_token"
            ],
            "representative_3_local_ms_per_token": typical[
                "projected_saved_ms_per_token"
            ],
            "passed": eager_passed
            and graph_passed
            and worst_route["projected_saved_ms_per_token"]
            >= (0.50 if tile_candidate else 0.30),
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
    baseline_gemm1_graph.reset()
    baseline_gemm2_graph.reset()
    candidate_gemm1_graph.reset()
    candidate_gemm2_graph.reset()
    torch.xpu.synchronize()
    return 0 if eager_passed and graph_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
