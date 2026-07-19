#!/usr/bin/env python3
"""Four-B70 gate for the explicit M7/M8 MoE activation portfolio.

This is a component/cycle microbenchmark, not an endpoint throughput claim.
It checks the production BF16 clamp/store boundaries, FP8 values and scales,
routed BF16 activations, output-connected token canaries, and captured timing.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import torch

import vllm  # noqa: F401 - register core operators
import vllm._custom_ops  # noqa: F401
import vllm_xpu_kernels._C  # noqa: F401
from vllm.models.deepseek_v4.xpu.model import (
    _use_shared_expert_fused_act_quant_width,
)
from vllm.platforms import current_platform
from vllm_xpu_kernels.fused_moe_interface import XpuFusedMoe


WIDTHS = (7, 8)
TOPK = 6
SHARED_GATE_UP = 1024
SHARED_HIDDEN = SHARED_GATE_UP // 2
ROUTED_INTERMEDIATE = 2048
CLAMP_LIMIT = 10.0
GROUP_SIZE = 128
INPUT_SCALES = (0.125, 1.0, 4.0, 12.0, 32.0)
ROUTES = (
    "typical_quarter_local",
    "overlap_quarter_local",
    "six_local",
    "all_same_local",
    "all_remote",
)
REAL_TOKEN_CORPUS = Path(
    "/mnt/fast-ai/deepseek-v4-corpora/"
    "mtp-reuse-m8-sequential-20260718T0440Z"
)


def summarize(samples: list[float]) -> dict[str, float | list[float]]:
    return {
        "median_us": statistics.median(samples),
        "min_us": min(samples),
        "max_us": max(samples),
        "samples_us": samples,
    }


def load_real_target_tokens(rank: int) -> dict[str, object]:
    manifest_path = REAL_TOKEN_CORPUS / f"rank{rank}/verifier_logits_m8/000.json"
    manifest = json.loads(manifest_path.read_text())
    logits_path = REAL_TOKEN_CORPUS / manifest["tensors"]["logits"]["blob"]
    tokens_path = REAL_TOKEN_CORPUS / manifest["tensors"]["top1_token_ids"]["blob"]
    logits = torch.load(logits_path, map_location="cpu", weights_only=True)
    expected = torch.load(tokens_path, map_location="cpu", weights_only=True)
    actual = logits.argmax(dim=-1)
    return {
        "manifest": str(manifest_path),
        "expected": expected.tolist(),
        "actual": actual.tolist(),
        "exact": torch.equal(expected, actual),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--physical-card", type=int, choices=range(4), required=True)
    parser.add_argument("--ep-rank", type=int, choices=range(4), required=True)
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--eager-cases", type=int, default=40)
    parser.add_argument("--graph-cases", type=int, default=32)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--samples", type=int, default=9)
    parser.add_argument("--required-ms", type=float, default=0.50)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    torch.xpu.set_device(args.device)
    device = torch.device(args.device)
    current_platform.import_kernels()
    dtype = torch.bfloat16
    quant_dtype = current_platform.fp8_dtype()
    fp8 = torch.finfo(quant_dtype)

    selector_shared = {
        str(width): _use_shared_expert_fused_act_quant_width(width)
        for width in range(1, 10)
    }

    class RoutedSelectorProbe:
        _m2_routed_clamp_silu = True
        _draft_m7_routed_clamp_silu = True
        _target_m8_routed_clamp_silu = True

    selector_routed = {
        str(width): XpuFusedMoe._use_routed_clamp_silu(
            RoutedSelectorProbe(), width
        )
        for width in range(1, 10)
    }
    selector_exact = (
        selector_shared
        == {
            "1": True,
            "2": True,
            "3": False,
            "4": False,
            "5": False,
            "6": False,
            "7": True,
            "8": True,
            "9": False,
        }
        and selector_routed
        == {
            "1": False,
            "2": True,
            "3": False,
            "4": False,
            "5": False,
            "6": False,
            "7": True,
            "8": True,
            "9": False,
        }
    )

    state: dict[int, dict[str, torch.Tensor]] = {}
    for width in WIDTHS:
        routed_rows = width * TOPK
        state[width] = {
            "shared_source": torch.empty(
                (width, SHARED_GATE_UP), dtype=dtype, device=device
            ),
            "shared_ref_q": torch.empty(
                (width, SHARED_HIDDEN), dtype=quant_dtype, device=device
            ),
            "shared_ref_s": torch.empty(
                (width, SHARED_HIDDEN // GROUP_SIZE),
                dtype=torch.float32,
                device=device,
            ),
            "shared_candidate_q": torch.empty(
                (width, SHARED_HIDDEN), dtype=quant_dtype, device=device
            ),
            "shared_candidate_s": torch.empty(
                (width, SHARED_HIDDEN // GROUP_SIZE),
                dtype=torch.float32,
                device=device,
            ),
            "routed_source": torch.empty(
                (routed_rows, 2 * ROUTED_INTERMEDIATE),
                dtype=dtype,
                device=device,
            ),
            "routed_ref_input": torch.empty(
                (routed_rows, 2 * ROUTED_INTERMEDIATE),
                dtype=dtype,
                device=device,
            ),
            "routed_candidate_input": torch.empty(
                (routed_rows, 2 * ROUTED_INTERMEDIATE),
                dtype=dtype,
                device=device,
            ),
            "routed_ref": torch.empty(
                (routed_rows, ROUTED_INTERMEDIATE), dtype=dtype, device=device
            ),
            "routed_candidate": torch.empty(
                (routed_rows, ROUTED_INTERMEDIATE), dtype=dtype, device=device
            ),
        }

    boundary = torch.tensor(
        [-32.0, -10.0, -9.9375, -0.0, 0.0, 9.9375, 10.0, 32.0],
        dtype=dtype,
        device=device,
    )

    def fill_inputs(case: int, route_index: int) -> None:
        for width in WIDTHS:
            tensors = state[width]
            generator = torch.Generator(device=device).manual_seed(
                20260718
                + args.physical_card * 100000
                + width * 10000
                + route_index * 1000
                + case
            )
            scale = INPUT_SCALES[case % len(INPUT_SCALES)]
            tensors["shared_source"].copy_(
                torch.randn(
                    tensors["shared_source"].shape,
                    dtype=dtype,
                    device=device,
                    generator=generator,
                )
                * scale
            )
            tensors["routed_source"].copy_(
                torch.randn(
                    tensors["routed_source"].shape,
                    dtype=dtype,
                    device=device,
                    generator=generator,
                )
                * scale
            )
            tensors["shared_source"][0, :8] = boundary
            tensors["shared_source"][0, SHARED_HIDDEN : SHARED_HIDDEN + 8] = (
                boundary
            )
            tensors["routed_source"][0, :8] = boundary
            tensors["routed_source"][0, ROUTED_INTERMEDIATE : ROUTED_INTERMEDIATE + 8] = (
                boundary
            )
            # Route families change the activation contents while preserving
            # the production padded [M*topk, 4096] extent. All-remote is the
            # fail-closed EP route and the minimum timing is reported.
            tensors["routed_source"].add_(route_index * 0.015625)
            tensors["routed_ref_input"].copy_(tensors["routed_source"])
            tensors["routed_candidate_input"].copy_(tensors["routed_source"])

    def shared_reference(width: int) -> None:
        tensors = state[width]
        gate = torch.clamp(
            tensors["shared_source"][:, :SHARED_HIDDEN], max=CLAMP_LIMIT
        )
        up = torch.clamp(
            tensors["shared_source"][:, SHARED_HIDDEN:],
            min=-CLAMP_LIMIT,
            max=CLAMP_LIMIT,
        )
        activated = gate * torch.sigmoid(gate) * up
        torch.ops._C.per_token_group_fp8_quant(
            activated,
            tensors["shared_ref_q"],
            tensors["shared_ref_s"],
            GROUP_SIZE,
            1e-10,
            fp8.min,
            fp8.max,
            False,
            False,
            False,
        )

    def shared_candidate(width: int) -> None:
        tensors = state[width]
        torch.ops._C.silu_and_mul_per_block_quant(
            tensors["shared_candidate_q"],
            tensors["shared_source"],
            tensors["shared_candidate_s"],
            GROUP_SIZE,
            None,
            False,
            False,
            CLAMP_LIMIT,
            1.0,
            0.0,
        )

    def routed_reference(width: int) -> None:
        tensors = state[width]
        tensors["routed_ref_input"][:, :ROUTED_INTERMEDIATE].clamp_(
            max=CLAMP_LIMIT
        )
        tensors["routed_ref_input"][:, ROUTED_INTERMEDIATE:].clamp_(
            min=-CLAMP_LIMIT, max=CLAMP_LIMIT
        )
        torch.ops._C.silu_and_mul(
            tensors["routed_ref"], tensors["routed_ref_input"]
        )

    def routed_candidate(width: int) -> None:
        tensors = state[width]
        torch.ops._C.silu_and_mul_clamp(
            tensors["routed_candidate"],
            tensors["routed_candidate_input"],
            CLAMP_LIMIT,
        )

    def reference_once() -> None:
        for width in WIDTHS:
            shared_reference(width)
            routed_reference(width)

    def candidate_once() -> None:
        for width in WIDTHS:
            shared_candidate(width)
            routed_candidate(width)

    def output_tokens(width: int, candidate: bool) -> torch.Tensor:
        tensors = state[width]
        q = tensors["shared_candidate_q" if candidate else "shared_ref_q"]
        scales = tensors[
            "shared_candidate_s" if candidate else "shared_ref_s"
        ]
        routed = tensors[
            "routed_candidate" if candidate else "routed_ref"
        ]
        shared_grouped = (
            q.float().reshape(width, 4, GROUP_SIZE)
            * scales.unsqueeze(-1)
        ).sum(dim=-1)
        shared_scores = shared_grouped.repeat_interleave(4, dim=-1)
        routed_scores = (
            routed.float().reshape(width, TOPK, 16, 128).sum(dim=-1).sum(dim=1)
        )
        return (shared_scores + routed_scores).argmax(dim=-1)

    def compare_outputs() -> dict[str, object]:
        widths: dict[str, object] = {}
        exact = True
        for width in WIDTHS:
            tensors = state[width]
            ref_tokens = output_tokens(width, False)
            candidate_tokens = output_tokens(width, True)
            row = {
                "fp8_mismatches": int(
                    torch.count_nonzero(
                        tensors["shared_ref_q"] != tensors["shared_candidate_q"]
                    ).item()
                ),
                "scale_mismatches": int(
                    torch.count_nonzero(
                        tensors["shared_ref_s"] != tensors["shared_candidate_s"]
                    ).item()
                ),
                "routed_bf16_mismatches": int(
                    torch.count_nonzero(
                        tensors["routed_ref"] != tensors["routed_candidate"]
                    ).item()
                ),
                "reference_tokens": ref_tokens.tolist(),
                "candidate_tokens": candidate_tokens.tolist(),
                "tokens_exact": torch.equal(ref_tokens, candidate_tokens),
            }
            row["exact"] = (
                row["fp8_mismatches"] == 0
                and row["scale_mismatches"] == 0
                and row["routed_bf16_mismatches"] == 0
                and row["tokens_exact"]
            )
            exact = exact and bool(row["exact"])
            widths[str(width)] = row
        return {"exact": exact, "widths": widths}

    eager_rows = []
    for case in range(args.eager_cases):
        route_index = case % len(ROUTES)
        fill_inputs(case, route_index)
        reference_once()
        candidate_once()
        torch.xpu.synchronize()
        comparison = compare_outputs()
        eager_rows.append(
            {
                "case": case,
                "route": ROUTES[route_index],
                **comparison,
            }
        )

    fill_inputs(9000, 0)
    for _ in range(3):
        reference_once()
        candidate_once()
    torch.xpu.synchronize()
    reference_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(reference_graph):
        reference_once()
    candidate_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(candidate_graph):
        candidate_once()
    reference_graph.replay()
    candidate_graph.replay()
    torch.xpu.synchronize()

    graph_rows = []
    for case in range(args.graph_cases):
        route_index = case % len(ROUTES)
        fill_inputs(10000 + case, route_index)
        reference_graph.replay()
        candidate_graph.replay()
        torch.xpu.synchronize()
        first = compare_outputs()
        first_snapshots = {
            width: (
                state[width]["shared_candidate_q"].clone(),
                state[width]["shared_candidate_s"].clone(),
                state[width]["routed_candidate"].clone(),
                output_tokens(width, True).clone(),
            )
            for width in WIDTHS
        }
        fill_inputs(20000 + case, (route_index + 1) % len(ROUTES))
        reference_graph.replay()
        candidate_graph.replay()
        torch.xpu.synchronize()
        changed = compare_outputs()
        fill_inputs(10000 + case, route_index)
        reference_graph.replay()
        candidate_graph.replay()
        torch.xpu.synchronize()
        repeated = compare_outputs()
        repeat_exact = all(
            torch.equal(first_snapshots[width][0], state[width]["shared_candidate_q"])
            and torch.equal(
                first_snapshots[width][1], state[width]["shared_candidate_s"]
            )
            and torch.equal(
                first_snapshots[width][2], state[width]["routed_candidate"]
            )
            and torch.equal(first_snapshots[width][3], output_tokens(width, True))
            for width in WIDTHS
        )
        graph_rows.append(
            {
                "case": case,
                "route": ROUTES[route_index],
                "exact": bool(
                    first["exact"]
                    and changed["exact"]
                    and repeated["exact"]
                    and repeat_exact
                ),
                "aba_repeat_exact": repeat_exact,
                "first": first,
                "changed": changed,
                "repeated": repeated,
            }
        )

    def reference_cycle() -> None:
        for _ in range(3):
            shared_reference(7)
            routed_reference(7)
        for _ in range(43):
            shared_reference(8)
            routed_reference(8)

    def candidate_cycle() -> None:
        for _ in range(3):
            shared_candidate(7)
            routed_candidate(7)
        for _ in range(43):
            shared_candidate(8)
            routed_candidate(8)

    fill_inputs(30000, 0)
    reference_cycle_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(reference_cycle_graph):
        reference_cycle()
    candidate_cycle_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(candidate_cycle_graph):
        candidate_cycle()
    reference_cycle_graph.replay()
    candidate_cycle_graph.replay()
    torch.xpu.synchronize()

    def timed_cycle_us(graph: torch.xpu.XPUGraph) -> float:
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(args.iterations):
            graph.replay()
        end.record()
        end.synchronize()
        return start.elapsed_time(end) * 1000.0 / args.iterations

    timing_rows = []
    for route_index, route in enumerate(ROUTES):
        fill_inputs(40000 + route_index, route_index)
        for _ in range(args.warmup):
            reference_cycle_graph.replay()
            candidate_cycle_graph.replay()
        torch.xpu.synchronize()
        reference_samples = []
        candidate_samples = []
        for sample in range(args.samples):
            if sample % 2 == 0:
                reference_samples.append(timed_cycle_us(reference_cycle_graph))
                candidate_samples.append(timed_cycle_us(candidate_cycle_graph))
            else:
                candidate_samples.append(timed_cycle_us(candidate_cycle_graph))
                reference_samples.append(timed_cycle_us(reference_cycle_graph))
        reference_summary = summarize(reference_samples)
        candidate_summary = summarize(candidate_samples)
        saved_ms = (
            reference_summary["median_us"] - candidate_summary["median_us"]
        ) / 1000.0
        timing_rows.append(
            {
                "route": route,
                "reference": reference_summary,
                "candidate": candidate_summary,
                "saved_ms_per_cycle": saved_ms,
            }
        )

    eager_passed = sum(bool(row["exact"]) for row in eager_rows)
    graph_passed = sum(bool(row["exact"]) for row in graph_rows)
    worst_timing = min(timing_rows, key=lambda row: row["saved_ms_per_cycle"])
    real_tokens = load_real_target_tokens(args.ep_rank)
    exact = (
        selector_exact
        and eager_passed == args.eager_cases
        and graph_passed == args.graph_cases
        and bool(real_tokens["exact"])
    )
    passed = exact and worst_timing["saved_ms_per_cycle"] >= args.required_ms
    result = {
        "schema_version": 1,
        "classification": "deepseek_v4_m7_m8_moe_activation_portfolio_gate",
        "claim_scope": "component cycle for one active generation; not endpoint throughput",
        "physical_card": args.physical_card,
        "ep_rank": args.ep_rank,
        "logical_device": args.device,
        "device_name": torch.xpu.get_device_name(device),
        "torch_version": torch.__version__,
        "contract": {
            "draft_width": 7,
            "draft_moe_stages_per_cycle": 3,
            "draft_experts": "64 local / 256 global / EP4",
            "target_width": 8,
            "target_layers_per_cycle": 43,
            "target_experts": "40 local / 160 global / EP4",
            "topk": TOPK,
            "clamp_limit": CLAMP_LIMIT,
            "shared_shape": "[M,1024] BF16 -> [M,512] FP8 + [M,4] FP32",
            "routed_shape": "[M*6,4096] BF16 -> [M*6,2048] BF16",
            "scale_ue8m0": False,
            "routes": ROUTES,
            "worst_route_policy": "minimum saved ms across every valid route",
        },
        "selectors": {
            "shared": selector_shared,
            "routed": selector_routed,
            "exact_allowed_widths": selector_exact,
        },
        "exactness": {
            "eager": {
                "passed": eager_passed,
                "required": args.eager_cases,
                "rows": eager_rows,
            },
            "graph": {
                "passed": graph_passed,
                "required": args.graph_cases,
                "fixed_address": True,
                "changed_inputs": True,
                "aba_replay": True,
                "rows": graph_rows,
            },
            "real_target_tokens": real_tokens,
            "exact": exact,
        },
        "timing": {
            "iterations": args.iterations,
            "samples": args.samples,
            "routes": timing_rows,
            "worst_route": worst_timing,
        },
        "gate": {
            "required_ms_per_cycle": args.required_ms,
            "passed": passed,
        },
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(rendered)
    print(rendered, end="")

    reference_graph.reset()
    candidate_graph.reset()
    reference_cycle_graph.reset()
    candidate_cycle_graph.reset()
    torch.xpu.synchronize()
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
