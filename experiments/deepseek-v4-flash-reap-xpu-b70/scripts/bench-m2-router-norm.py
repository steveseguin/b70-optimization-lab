#!/usr/bin/env python3
"""Gate fused M=2/4/8 biased top-k, normalization, and routed scaling."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics

import torch

from vllm.platforms import current_platform


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--width", type=int, choices=(2, 4, 8), default=2)
    parser.add_argument("--experts", type=int, default=160)
    parser.add_argument("--topk", type=int, default=6)
    parser.add_argument("--layers", type=int, default=40)
    parser.add_argument("--scaling", type=float, default=1.5)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--graph-epochs", type=int, default=32)
    parser.add_argument("--warmup", type=int, default=100)
    parser.add_argument("--batches", type=int, default=10)
    parser.add_argument("--batch-iterations", type=int, default=200)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    torch.xpu.set_device(args.device)
    torch.manual_seed(20260716)
    device = torch.device(args.device)
    current_platform.import_kernels()

    scores = torch.empty(
        (args.width, args.experts), dtype=torch.float32, device=device
    )
    bias = torch.randn((args.experts,), dtype=torch.float32, device=device)
    bias.mul_(0.02).add_(8.08)
    reference_weights = torch.empty(
        (args.width, args.topk), dtype=torch.float32, device=device
    )
    reference_ids = torch.empty(
        (args.width, args.topk), dtype=torch.int32, device=device
    )
    candidate_weights = torch.empty_like(reference_weights)
    candidate_ids = torch.empty_like(reference_ids)

    def reference() -> tuple[torch.Tensor, torch.Tensor]:
        scores_for_choice = scores + bias.float()
        indices = torch.topk(
            scores_for_choice,
            k=args.topk,
            dim=-1,
            sorted=True,
        ).indices
        reference_ids.copy_(indices)
        weights = scores.gather(1, indices)
        weights = weights / weights.sum(dim=-1, keepdim=True).clamp(min=1e-20)
        reference_weights.copy_(weights * args.scaling)
        return reference_weights, reference_ids

    def candidate() -> tuple[torch.Tensor, torch.Tensor]:
        torch.ops._xpu_C.deepseek_m2_biased_topk_norm_out(
            candidate_weights,
            candidate_ids,
            scores,
            bias,
            args.scaling,
        )
        return candidate_weights, candidate_ids

    def compare(epoch: int) -> dict[str, int | float]:
        expected_weights, expected_ids = reference()
        got_weights, got_ids = candidate()
        torch.xpu.synchronize()
        return {
            "epoch": epoch,
            "id_mismatches": int(
                torch.count_nonzero(expected_ids != got_ids).item()
            ),
            "weight_mismatches": int(
                torch.count_nonzero(expected_weights != got_weights).item()
            ),
            "max_abs_weight_difference": float(
                (expected_weights - got_weights).abs().max().item()
            ),
        }

    changed_rows = []
    for epoch in range(args.epochs):
        generator = torch.Generator(device=device)
        generator.manual_seed(20260716 + epoch)
        scores.copy_(
            torch.rand(
                scores.shape,
                dtype=scores.dtype,
                device=device,
                generator=generator,
            )
            * (0.5 + 0.125 * (epoch % 7))
        )
        changed_rows.append(compare(epoch))

    def timed_us(call) -> float:
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(args.batch_iterations):
            call()
        end.record()
        end.synchronize()
        return start.elapsed_time(end) * 1000.0 / args.batch_iterations

    for _ in range(args.warmup):
        reference()
        candidate()
    torch.xpu.synchronize()

    reference_us = []
    candidate_us = []
    for batch in range(args.batches):
        if batch % 2 == 0:
            reference_us.append(timed_us(reference))
            candidate_us.append(timed_us(candidate))
        else:
            candidate_us.append(timed_us(candidate))
            reference_us.append(timed_us(reference))

    reference_median = statistics.median(reference_us)
    candidate_median = statistics.median(candidate_us)
    projected_saved_ms = (
        (reference_median - candidate_median) * args.layers / 1000.0
    )
    exact = all(
        row["id_mismatches"] == 0 and row["weight_mismatches"] == 0
        for row in changed_rows
    )

    reference_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(reference_graph):
        reference()
    candidate_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(candidate_graph):
        candidate()
    reference_graph.replay()
    candidate_graph.replay()
    torch.xpu.synchronize()

    graph_rows = []
    for epoch in range(args.graph_epochs):
        generator = torch.Generator(device=device)
        generator.manual_seed(20261716 + epoch)
        scores.copy_(
            torch.rand(
                scores.shape,
                dtype=scores.dtype,
                device=device,
                generator=generator,
            )
            * (0.5 + 0.125 * (epoch % 7))
        )
        reference_graph.replay()
        candidate_graph.replay()
        torch.xpu.synchronize()
        graph_rows.append(
            {
                "id_mismatches": int(
                    torch.count_nonzero(reference_ids != candidate_ids).item()
                ),
                "weight_mismatches": int(
                    torch.count_nonzero(
                        reference_weights != candidate_weights
                    ).item()
                ),
            }
        )

    def timed_graph_us(graph: torch.xpu.XPUGraph) -> float:
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(args.batch_iterations):
            graph.replay()
        end.record()
        end.synchronize()
        return start.elapsed_time(end) * 1000.0 / args.batch_iterations

    reference_graph_us = []
    candidate_graph_us = []
    for batch in range(args.batches):
        if batch % 2 == 0:
            reference_graph_us.append(timed_graph_us(reference_graph))
            candidate_graph_us.append(timed_graph_us(candidate_graph))
        else:
            candidate_graph_us.append(timed_graph_us(candidate_graph))
            reference_graph_us.append(timed_graph_us(reference_graph))
    reference_graph_median = statistics.median(reference_graph_us)
    candidate_graph_median = statistics.median(candidate_graph_us)
    graph_saved_ms = (
        (reference_graph_median - candidate_graph_median)
        * args.layers
        / 1000.0
    )
    graph_exact = all(
        row["id_mismatches"] == 0 and row["weight_mismatches"] == 0
        for row in graph_rows
    )
    result = {
        "schema_version": 1,
        "classification": "deepseek_v4_mwidth_router_norm_microgate",
        "device": args.device,
        "device_name": torch.xpu.get_device_name(device),
        "torch_version": torch.__version__,
        "shape": {
            "m": args.width,
            "experts": args.experts,
            "topk": args.topk,
        },
        "routed_scaling_factor": args.scaling,
        "changed_input_gate": {
            "epochs": args.epochs,
            "exact_epochs": sum(
                row["id_mismatches"] == 0
                and row["weight_mismatches"] == 0
                for row in changed_rows
            ),
            "total_id_mismatches": sum(
                row["id_mismatches"] for row in changed_rows
            ),
            "total_weight_mismatches": sum(
                row["weight_mismatches"] for row in changed_rows
            ),
            "maximum_abs_weight_difference": max(
                row["max_abs_weight_difference"] for row in changed_rows
            ),
        },
        "timing": {
            "warmup": args.warmup,
            "batches": args.batches,
            "batch_iterations": args.batch_iterations,
            "reference_us": {
                "median": reference_median,
                "samples": reference_us,
            },
            "candidate_us": {
                "median": candidate_median,
                "samples": candidate_us,
            },
            "speedup": reference_median / candidate_median,
            "projected_saved_ms_per_cycle": projected_saved_ms,
        },
        "graph_replay_gate": {
            "epochs": args.graph_epochs,
            "exact_epochs": sum(
                row["id_mismatches"] == 0
                and row["weight_mismatches"] == 0
                for row in graph_rows
            ),
            "total_id_mismatches": sum(
                row["id_mismatches"] for row in graph_rows
            ),
            "total_weight_mismatches": sum(
                row["weight_mismatches"] for row in graph_rows
            ),
            "reference_us": {
                "median": reference_graph_median,
                "samples": reference_graph_us,
            },
            "candidate_us": {
                "median": candidate_graph_median,
                "samples": candidate_graph_us,
            },
            "projected_saved_ms_per_cycle": graph_saved_ms,
            "passes_0_5ms_gate": graph_exact and graph_saved_ms >= 0.5,
        },
        "gate": {
            "minimum_projected_saved_ms_per_cycle": 0.5,
            "requires_bitwise_ids_and_weights": True,
            "passes": exact
            and projected_saved_ms >= 0.5
            and graph_exact
            and graph_saved_ms >= 0.5,
        },
    }
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n")
    return 0 if result["gate"]["passes"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
