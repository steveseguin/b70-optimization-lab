#!/usr/bin/env python3
"""Gate M=2 router emission of a deduplicated token/expert route table."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics

import torch

from vllm.platforms import current_platform


def expected_routes(ids: torch.Tensor) -> tuple[list[int], list[int], list[int]]:
    rows = ids.cpu().tolist()
    unique_experts: list[int] = []
    token_masks: list[int] = []
    slot_to_unique: list[int] = []
    for token, token_ids in enumerate(rows):
        for expert in token_ids:
            if expert in unique_experts:
                unique = unique_experts.index(expert)
            else:
                unique = len(unique_experts)
                unique_experts.append(expert)
                token_masks.append(0)
            token_masks[unique] |= 1 << token
            slot_to_unique.append(unique)
    return unique_experts, token_masks, slot_to_unique


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--graph-epochs", type=int, default=32)
    parser.add_argument("--warmup", type=int, default=100)
    parser.add_argument("--batches", type=int, default=10)
    parser.add_argument("--batch-iterations", type=int, default=500)
    parser.add_argument("--layers", type=int, default=40)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    torch.xpu.set_device(args.device)
    device = torch.device(args.device)
    current_platform.import_kernels()
    torch.manual_seed(20260716)

    scores = torch.empty((2, 160), dtype=torch.float32, device=device)
    bias = torch.randn((160,), dtype=torch.float32, device=device)
    bias.mul_(0.02).add_(8.08)
    control_weights = torch.empty((2, 6), dtype=torch.float32, device=device)
    control_ids = torch.empty((2, 6), dtype=torch.int32, device=device)
    candidate_weights = torch.empty_like(control_weights)
    candidate_ids = torch.empty_like(control_ids)
    unique_experts = torch.empty((12,), dtype=torch.int32, device=device)
    unique_token_masks = torch.empty_like(unique_experts)
    slot_to_unique = torch.empty_like(unique_experts)
    unique_count = torch.empty((1,), dtype=torch.int32, device=device)

    def control() -> None:
        torch.ops._xpu_C.deepseek_m2_biased_topk_norm_out(
            control_weights, control_ids, scores, bias, 1.5
        )

    def candidate() -> None:
        torch.ops._xpu_C.deepseek_m2_biased_topk_norm_routes_out(
            candidate_weights,
            candidate_ids,
            unique_experts,
            unique_token_masks,
            slot_to_unique,
            unique_count,
            scores,
            bias,
            1.5,
        )

    def update_scores(epoch: int, offset: int = 0) -> None:
        generator = torch.Generator(device=device).manual_seed(
            20260716 + offset + epoch
        )
        scores.copy_(
            torch.rand(
                scores.shape,
                dtype=scores.dtype,
                device=device,
                generator=generator,
            )
            * (0.5 + 0.125 * (epoch % 7))
        )

    def compare(epoch: int, execute: bool = True) -> dict[str, int | bool]:
        if execute:
            control()
            candidate()
            torch.xpu.synchronize()
        expected_experts, expected_masks, expected_slots = expected_routes(
            control_ids
        )
        count = int(unique_count.item())
        got_experts = unique_experts.cpu().tolist()
        got_masks = unique_token_masks.cpu().tolist()
        got_slots = slot_to_unique.cpu().tolist()
        return {
            "epoch": epoch,
            "weights_exact": torch.equal(control_weights, candidate_weights),
            "ids_exact": torch.equal(control_ids, candidate_ids),
            "count": count,
            "count_exact": count == len(expected_experts),
            "experts_exact": got_experts[:count] == expected_experts,
            "masks_exact": got_masks[:count] == expected_masks,
            "tail_initialized": all(value == -1 for value in got_experts[count:])
            and all(value == 0 for value in got_masks[count:]),
            "slots_exact": got_slots == expected_slots,
        }

    eager_rows = []
    for epoch in range(args.epochs):
        update_scores(epoch)
        eager_rows.append(compare(epoch))

    control_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(control_graph):
        control()
    candidate_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(candidate_graph):
        candidate()
    control_graph.replay()
    candidate_graph.replay()
    torch.xpu.synchronize()

    graph_rows = []
    for epoch in range(args.graph_epochs):
        update_scores(epoch, 10000)
        control_graph.replay()
        candidate_graph.replay()
        torch.xpu.synchronize()
        graph_rows.append(compare(epoch, execute=False))

    def timed_us(graph: torch.xpu.XPUGraph) -> float:
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(args.batch_iterations):
            graph.replay()
        end.record()
        end.synchronize()
        return start.elapsed_time(end) * 1000.0 / args.batch_iterations

    for _ in range(args.warmup):
        control_graph.replay()
        candidate_graph.replay()
    torch.xpu.synchronize()
    control_samples = []
    candidate_samples = []
    for batch in range(args.batches):
        if batch % 2 == 0:
            control_samples.append(timed_us(control_graph))
            candidate_samples.append(timed_us(candidate_graph))
        else:
            candidate_samples.append(timed_us(candidate_graph))
            control_samples.append(timed_us(control_graph))

    control_median = statistics.median(control_samples)
    candidate_median = statistics.median(candidate_samples)
    overhead_us = candidate_median - control_median

    def exact(rows: list[dict[str, int | bool]]) -> bool:
        return all(
            all(value for key, value in row.items() if key.endswith("exact"))
            and row["tail_initialized"]
            for row in rows
        )

    result = {
        "schema_version": 1,
        "classification": "deepseek_v4_m2_router_unique_routes_gate",
        "device": args.device,
        "device_name": torch.xpu.get_device_name(device),
        "shape": {"m": 2, "experts": 160, "topk": 6},
        "correctness": {
            "eager_epochs": args.epochs,
            "eager_exact": exact(eager_rows),
            "graph_epochs": args.graph_epochs,
            "graph_exact": exact(graph_rows),
            "eager_rows": eager_rows,
            "graph_rows": graph_rows,
        },
        "timing": {
            "control_median_us": control_median,
            "candidate_median_us": candidate_median,
            "route_table_overhead_us_per_layer": overhead_us,
            "projected_overhead_ms_per_cycle": overhead_us
            * args.layers
            / 1000.0,
            "control_samples_us": control_samples,
            "candidate_samples_us": candidate_samples,
        },
        "passed": exact(eager_rows) and exact(graph_rows),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
