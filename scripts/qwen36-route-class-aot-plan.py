#!/usr/bin/env python3
"""Plan route-class AOT/persistent MoE candidates from Qwen3.6 route JSONL.

This is a CPU-only planning gate. It consumes captured route rows and estimates
whether a small exact route-specialized micro-library is plausible before we
spend XPU time building kernels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


DEFAULT_CONFIG = (
    "/mnt/fast-ai/llm-cache/hf/"
    "models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/"
    "snapshots/cced56592e8c8935f8220836b4baa04dfd389118/config.json"
)


def read_jsonl(path: str) -> list[dict[str, Any]]:
    rows = []
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_text_config(path: str) -> dict[str, Any]:
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    text_config = cfg.get("text_config")
    if not isinstance(text_config, dict):
        raise ValueError(f"Missing text_config in {path}")
    return text_config


def route_tuple(record: dict[str, Any]) -> tuple[int, ...] | None:
    topk_ids = record.get("topk_ids")
    if not isinstance(topk_ids, list) or not topk_ids:
        return None
    first = topk_ids[0]
    if not isinstance(first, list):
        return None
    return tuple(int(item) for item in first)


def stable_route_hash(route: tuple[int, ...]) -> str:
    payload = ",".join(str(item) for item in route).encode("utf-8")
    return hashlib.blake2s(payload, digest_size=8).hexdigest()


def layer_key(record: dict[str, Any]) -> str:
    layer_index = record.get("layer_index")
    if layer_index is not None:
        return f"layer_{int(layer_index):02d}"
    return str(record.get("layer") or "unknown")


def parse_budgets(value: str) -> list[int]:
    budgets = []
    for item in value.split(","):
        item = item.strip()
        if item:
            budgets.append(int(item))
    if not budgets:
        raise argparse.ArgumentTypeError("at least one budget is required")
    return sorted(set(budgets))


def expert_shard_bytes(text_config: dict[str, Any], tp_size: int) -> dict[str, Any]:
    hidden_size = int(text_config["hidden_size"])
    full_inter = int(text_config["moe_intermediate_size"])
    inter = full_inter // tp_size
    w13_bytes = hidden_size * (2 * inter)
    w2_bytes = inter * hidden_size
    w13_scale_bytes = (2 * inter) * 4
    w2_scale_bytes = hidden_size * 4
    total = w13_bytes + w2_bytes + w13_scale_bytes + w2_scale_bytes
    return {
        "hidden_size": hidden_size,
        "moe_intermediate_size_full": full_inter,
        "moe_intermediate_size_tp_shard": inter,
        "tp_size": tp_size,
        "w13_int8_bytes_per_expert": w13_bytes,
        "w2_int8_bytes_per_expert": w2_bytes,
        "scale_bytes_per_expert": w13_scale_bytes + w2_scale_bytes,
        "total_bytes_per_expert_tp_shard": total,
        "total_mib_per_expert_tp_shard": total / (1024 * 1024),
    }


def coverage_for_budget(counter: Counter[tuple[int, ...]], budget: int) -> float:
    total = sum(counter.values())
    if total <= 0:
        return 0.0
    covered = sum(count for _, count in counter.most_common(budget))
    return covered / total


def summarize(records: list[dict[str, Any]],
              *,
              text_config: dict[str, Any],
              budgets: list[int],
              tp_size: int,
              min_fixture_events_for_decision: int) -> dict[str, Any]:
    by_layer: dict[str, Counter[tuple[int, ...]]] = defaultdict(Counter)
    layer_names: dict[str, str] = {}
    global_classes: Counter[tuple[int, ...]] = Counter()
    fixture_events = set()
    skipped = 0

    for record in records:
        topk = route_tuple(record)
        if topk is None:
            skipped += 1
            continue
        key = layer_key(record)
        by_layer[key][topk] += 1
        global_classes[topk] += 1
        layer_names[key] = str(record.get("layer") or key)
        if record.get("fixture_index") is not None:
            fixture_events.add(("fixture_index", record.get("fixture_index")))
        elif record.get("event_id") is not None:
            fixture_events.add(("event_id", record.get("event_id")))

    expert_bytes = expert_shard_bytes(text_config, tp_size)
    bytes_per_expert = int(expert_bytes["total_bytes_per_expert_tp_shard"])
    num_experts = int(text_config["num_experts"])
    layers = sorted(by_layer)
    layer_reports = []
    exact_class_count = 0
    exact_unique_hot_expert_pack_count = 0

    for layer in layers:
        counter = by_layer[layer]
        exact_class_count += len(counter)
        exact_hot_union = set()
        for route in counter:
            exact_hot_union.update(route)
        exact_unique_hot_expert_pack_count += len(exact_hot_union)

        coverage = {
            str(budget): coverage_for_budget(counter, budget)
            for budget in budgets
        }
        hot_union_by_budget = {}
        duplicate_experts_by_budget = {}
        for budget in budgets:
            selected = counter.most_common(budget)
            union = set()
            duplicate = 0
            for route, _ in selected:
                union.update(route)
                duplicate += len(route)
            hot_union_by_budget[str(budget)] = len(union)
            duplicate_experts_by_budget[str(budget)] = duplicate
        layer_reports.append({
            "layer_key": layer,
            "layer": layer_names[layer],
            "records": sum(counter.values()),
            "unique_route_classes": len(counter),
            "top_classes": [
                {
                    "topk_ids": list(route),
                    "count": count,
                    "coverage": count / sum(counter.values()),
                    "route_hash": stable_route_hash(route),
                }
                for route, count in counter.most_common(8)
            ],
            "coverage_by_budget": coverage,
            "hot_union_experts_by_budget": hot_union_by_budget,
            "duplicate_experts_by_budget": duplicate_experts_by_budget,
        })

    budget_summary = {}
    for budget in budgets:
        key = str(budget)
        coverages = [
            report["coverage_by_budget"][key] for report in layer_reports
        ]
        hot_union = [
            report["hot_union_experts_by_budget"][key]
            for report in layer_reports
        ]
        duplicate = [
            report["duplicate_experts_by_budget"][key]
            for report in layer_reports
        ]
        budget_summary[key] = {
            "mean_layer_coverage": mean(coverages) if coverages else 0.0,
            "min_layer_coverage": min(coverages) if coverages else 0.0,
            "max_layer_coverage": max(coverages) if coverages else 0.0,
            "total_unique_hot_expert_packs_across_layers": sum(hot_union),
            "total_duplicate_hot_expert_packs_across_layers": sum(duplicate),
            "unique_hot_pack_mib": sum(hot_union) * bytes_per_expert /
            (1024 * 1024),
            "duplicate_route_pack_mib": sum(duplicate) * bytes_per_expert /
            (1024 * 1024),
        }

    exact_pack_mib = exact_unique_hot_expert_pack_count * bytes_per_expert / (
        1024 * 1024)
    full_layer_shard_mib = (
        len(layers) * num_experts * bytes_per_expert / (1024 * 1024))
    fixture_event_count = len(fixture_events)
    if fixture_event_count < min_fixture_events_for_decision:
        status = "needs_more_route_windows_before_aot_commit"
    elif exact_class_count <= 128:
        status = "route_class_micro_library_promising"
    else:
        status = "route_class_micro_library_too_many_classes"

    return {
        "status": status,
        "records_total": len(records),
        "records_used": sum(sum(counter.values()) for counter in by_layer.values()),
        "records_skipped": skipped,
        "fixture_event_count": fixture_event_count,
        "min_fixture_events_for_decision": min_fixture_events_for_decision,
        "layer_count": len(layers),
        "global_unique_route_classes": len(global_classes),
        "per_layer_exact_route_class_count": exact_class_count,
        "per_layer_exact_route_class_mean":
        exact_class_count / max(1, len(layers)),
        "per_layer_exact_unique_hot_expert_pack_count":
        exact_unique_hot_expert_pack_count,
        "per_layer_exact_unique_hot_pack_mib": exact_pack_mib,
        "full_tp_shard_moe_weight_mib_for_seen_layers": full_layer_shard_mib,
        "exact_hot_pack_fraction_of_full_seen_layer_shards":
        (exact_pack_mib / full_layer_shard_mib if full_layer_shard_mib else None),
        "expert_shard_bytes": expert_bytes,
        "budget_summary": budget_summary,
        "global_top_route_classes": [
            {
                "topk_ids": list(route),
                "count": count,
                "coverage": count / max(1, sum(global_classes.values())),
                "route_hash": stable_route_hash(route),
            }
            for route, count in global_classes.most_common(16)
        ],
        "layers": layer_reports,
        "interpretation": (
            "This is an AOT planning gate only. It estimates route-class "
            "coverage and hot-pack memory from captured routes; it does not "
            "prove speed or quality. Kernel candidates still need graph-path "
            "tensor parity, prologue-inclusive timing, quality gates, and an "
            "accepted-lane manifest before endpoint promotion."
        ),
    }


def fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        return f"{value:.{digits}f}"
    return str(value)


def write_markdown(path: str, summary: dict[str, Any], budgets: list[int]) -> None:
    lines = [
        "# Qwen3.6 Route-Class AOT Plan",
        "",
        f"- Status: `{summary['status']}`.",
        f"- Records used: `{summary['records_used']}` / `{summary['records_total']}`.",
        f"- Fixture events: `{summary['fixture_event_count']}`.",
        f"- Layers: `{summary['layer_count']}`.",
        f"- Global unique route classes: `{summary['global_unique_route_classes']}`.",
        (
            "- Per-layer exact route classes: "
            f"`{summary['per_layer_exact_route_class_count']}` "
            f"(mean `{fmt(summary['per_layer_exact_route_class_mean'])}` per layer)."
        ),
        (
            "- Exact unique hot-pack memory for seen layers: "
            f"`{fmt(summary['per_layer_exact_unique_hot_pack_mib'])} MiB` "
            "per TP shard."
        ),
        (
            "- Exact hot-pack fraction of full seen-layer MoE shards: "
            f"`{fmt(summary['exact_hot_pack_fraction_of_full_seen_layer_shards'])}`."
        ),
        "",
        "## Budget Coverage",
        "",
        "| classes/layer | mean coverage | min coverage | unique hot-pack MiB | duplicate route-pack MiB |",
        "|---:|---:|---:|---:|---:|",
    ]
    for budget in budgets:
        row = summary["budget_summary"][str(budget)]
        lines.append(
            f"| {budget} | {fmt(row['mean_layer_coverage'])} | "
            f"{fmt(row['min_layer_coverage'])} | "
            f"{fmt(row['unique_hot_pack_mib'])} | "
            f"{fmt(row['duplicate_route_pack_mib'])} |"
        )
    lines.extend([
        "",
        "## Top Global Route Classes",
        "",
    ])
    for item in summary["global_top_route_classes"][:8]:
        lines.append(
            f"- `{item['route_hash']}` count `{item['count']}`, "
            f"coverage `{fmt(item['coverage'])}`, topk `{item['topk_ids']}`"
        )
    lines.extend([
        "",
        "## Layer Snapshot",
        "",
        "| layer | records | unique classes | top1 coverage | top2 coverage | top3 coverage |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for layer in summary["layers"][:40]:
        cov = layer["coverage_by_budget"]
        lines.append(
            f"| {layer['layer_key']} | {layer['records']} | "
            f"{layer['unique_route_classes']} | "
            f"{fmt(cov.get('1'))} | {fmt(cov.get('2'))} | {fmt(cov.get('3'))} |"
        )
    lines.extend(["", "## Interpretation", "", summary["interpretation"], ""])
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("route_jsonl")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--tp-size", type=int, default=4)
    parser.add_argument("--budgets", type=parse_budgets, default=parse_budgets("1,2,3,4,8"))
    parser.add_argument("--min-fixture-events-for-decision", type=int, default=10)
    parser.add_argument("--output-json")
    parser.add_argument("--markdown-out")
    args = parser.parse_args()

    records = read_jsonl(args.route_jsonl)
    summary = summarize(
        records,
        text_config=load_text_config(args.config),
        budgets=args.budgets,
        tp_size=args.tp_size,
        min_fixture_events_for_decision=args.min_fixture_events_for_decision,
    )
    text = json.dumps(summary, indent=2, sort_keys=True)
    if args.output_json:
        Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output_json).write_text(text + "\n", encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).parent.mkdir(parents=True, exist_ok=True)
        write_markdown(args.markdown_out, summary, args.budgets)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
