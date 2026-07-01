#!/usr/bin/env python3
"""Build exact hot-replicated route work queues from Qwen3.6 route captures.

This is a route-replay implementation prototype. It does not execute kernels.
It converts captured `topk_ids` into per-rank hot/cold queues and gather maps
that a one-layer hot-replicated MoE kernel path can consume.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


def parse_int_list(value: str) -> list[int]:
    out = []
    for item in value.split(","):
        item = item.strip()
        if item:
            out.append(int(item))
    if not out:
        raise argparse.ArgumentTypeError("expected at least one integer")
    return out


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    pos = (pct / 100.0) * (len(ordered) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return float(ordered[lo])
    frac = pos - lo
    return float(ordered[lo] * (1.0 - frac) + ordered[hi] * frac)


def summarize(values: list[float]) -> dict[str, float]:
    return {
        "mean": mean(values),
        "p50": percentile(values, 50),
        "p90": percentile(values, 90),
        "p95": percentile(values, 95),
        "min": min(values) if values else 0.0,
        "max": max(values) if values else 0.0,
    }


def load_records(
    path: str,
    *,
    layer_regex: str | None,
    stage_regex: str | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    layer_pattern = re.compile(layer_regex) if layer_regex else None
    stage_pattern = re.compile(stage_regex) if stage_regex else None
    records = []
    loaded = 0
    skipped = 0
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            loaded += 1
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSONL") from exc
            layer = str(record.get("layer") or "")
            stage = str(record.get("stage") or "")
            if layer_pattern and not layer_pattern.search(layer):
                skipped += 1
                continue
            if stage_pattern and not stage_pattern.search(stage):
                skipped += 1
                continue
            if not isinstance(record.get("topk_ids"), list):
                skipped += 1
                continue
            if not isinstance(record.get("counts"), list):
                skipped += 1
                continue
            record["_route_index"] = len(records)
            records.append(record)
    if not records:
        raise ValueError("No matching records with topk_ids")
    layers = sorted({str(record.get("layer") or "") for record in records})
    return records, {
        "route_jsonl": path,
        "records_loaded": loaded,
        "records_matched": len(records),
        "records_skipped": skipped,
        "layers": layers,
    }


def aggregate_counts(records: list[dict[str, Any]]) -> list[int]:
    counts = [0] * len(records[0]["counts"])
    for record in records:
        row_counts = [int(item) for item in record["counts"]]
        if len(row_counts) != len(counts):
            raise ValueError("record count length changed")
        for idx, value in enumerate(row_counts):
            counts[idx] += value
    return counts


def hotset_from_counts(counts: list[int], size: int) -> list[int]:
    return [
        expert
        for expert, count in sorted(
            enumerate(counts), key=lambda item: item[1], reverse=True
        )[:size]
        if count > 0
    ]


def validate_hotset(experts: list[int], num_experts: int) -> list[int]:
    seen = set()
    out = []
    for expert in experts:
        if expert < 0 or expert >= num_experts:
            raise ValueError(f"hotset expert outside valid range: {expert}")
        if expert in seen:
            raise ValueError(f"duplicate hotset expert: {expert}")
        seen.add(expert)
        out.append(expert)
    return out


def owner_map_greedy_excluding(
    layer_counts: list[int],
    ranks: int,
    excluded: set[int],
) -> list[int]:
    loads = [0] * ranks
    owners = [0] * len(layer_counts)
    for expert, count in sorted(
        enumerate(layer_counts), key=lambda item: item[1], reverse=True
    ):
        if expert in excluded:
            owners[expert] = -1
            continue
        owner = min(range(ranks), key=lambda idx: (loads[idx], idx))
        owners[expert] = owner
        loads[owner] += int(count)
    return owners


def select_windows(
    records: list[dict[str, Any]],
    *,
    start_indices: list[int],
    window_size: int,
) -> list[dict[str, Any]]:
    windows = []
    for start in start_indices:
        if start < 0 or start >= len(records):
            continue
        selected = records[start:start + window_size]
        if len(selected) < window_size:
            continue
        windows.append({
            "route_start_index": start,
            "route_window_size": window_size,
            "records": selected,
        })
    if not windows:
        raise ValueError("No windows selected")
    return windows


def flatten_assignments(records: list[dict[str, Any]]) -> list[dict[str, int]]:
    assignments = []
    row_id = 0
    token_row = 0
    for window_record_index, record in enumerate(records):
        topk_ids = record.get("topk_ids") or []
        top_k = int(record.get("top_k") or (len(topk_ids[0]) if topk_ids else 0))
        for local_token_index, row in enumerate(topk_ids):
            if not isinstance(row, list):
                raise ValueError("topk_ids row is not a list")
            if len(row) != top_k:
                raise ValueError("topk_ids row length changed")
            for topk_slot, expert in enumerate(row):
                assignments.append({
                    "row_id": row_id,
                    "token_row": token_row,
                    "window_record_index": window_record_index,
                    "route_record_index": int(record["_route_index"]),
                    "call": int(record.get("call") or 0),
                    "local_token_index": local_token_index,
                    "topk_slot": topk_slot,
                    "expert": int(expert),
                })
                row_id += 1
            token_row += 1
    return assignments


def build_window_plan(
    *,
    window: dict[str, Any],
    layer_counts: list[int],
    hotset: list[int],
    ranks: int,
    include_rows: bool,
) -> dict[str, Any]:
    hot_lookup = {expert: idx for idx, expert in enumerate(hotset)}
    hot_lookup_set = set(hot_lookup)
    cold_owners = owner_map_greedy_excluding(layer_counts, ranks, hot_lookup_set)
    assignments = flatten_assignments(window["records"])

    rank_queues = [
        {
            "rank": rank,
            "hot_rows": [],
            "cold_rows": [],
            "hot_counts_by_compact_expert": [0] * len(hotset),
            "cold_counts_by_logical_expert": defaultdict(int),
        }
        for rank in range(ranks)
    ]
    gather_map = []

    # Seed loads with cold rows so replicated hot rows are assigned to balance
    # total per-rank work for this window.
    rank_loads = [0] * ranks
    for assignment in assignments:
        expert = int(assignment["expert"])
        if expert not in hot_lookup_set:
            owner = cold_owners[expert]
            if owner < 0:
                raise ValueError("cold expert has no owner")
            rank_loads[owner] += 1

    for assignment in assignments:
        expert = int(assignment["expert"])
        if expert in hot_lookup_set:
            rank = min(range(ranks), key=lambda idx: (rank_loads[idx], idx))
            rank_loads[rank] += 1
            compact_expert = hot_lookup[expert]
            local_row = len(rank_queues[rank]["hot_rows"])
            row = {
                **assignment,
                "path": "hot",
                "rank": rank,
                "local_row": local_row,
                "compact_expert": compact_expert,
            }
            rank_queues[rank]["hot_rows"].append(row)
            rank_queues[rank]["hot_counts_by_compact_expert"][compact_expert] += 1
            gather_map.append({
                "row_id": assignment["row_id"],
                "path": "hot",
                "rank": rank,
                "local_row": local_row,
            })
        else:
            rank = cold_owners[expert]
            local_row = len(rank_queues[rank]["cold_rows"])
            row = {
                **assignment,
                "path": "cold",
                "rank": rank,
                "local_row": local_row,
                "logical_expert": expert,
            }
            rank_queues[rank]["cold_rows"].append(row)
            rank_queues[rank]["cold_counts_by_logical_expert"][expert] += 1
            gather_map.append({
                "row_id": assignment["row_id"],
                "path": "cold",
                "rank": rank,
                "local_row": local_row,
            })

    gather_map.sort(key=lambda item: item["row_id"])
    if [item["row_id"] for item in gather_map] != list(range(len(assignments))):
        raise ValueError("gather map is not a complete row_id permutation")

    rank_summaries = []
    for queue in rank_queues:
        hot_rows = queue["hot_rows"]
        cold_rows = queue["cold_rows"]
        hot_active = sum(1 for count in queue["hot_counts_by_compact_expert"] if count)
        cold_counts = dict(sorted(queue["cold_counts_by_logical_expert"].items()))
        rank_summaries.append({
            "rank": queue["rank"],
            "hot_rows": len(hot_rows),
            "cold_rows": len(cold_rows),
            "total_rows": len(hot_rows) + len(cold_rows),
            "hot_active_experts": hot_active,
            "cold_active_experts": len(cold_counts),
            "hot_counts_by_compact_expert": queue["hot_counts_by_compact_expert"],
            "cold_counts_by_logical_expert": cold_counts,
            "hot_rows_detail": hot_rows if include_rows else None,
            "cold_rows_detail": cold_rows if include_rows else None,
        })
    total_hot = sum(item["hot_rows"] for item in rank_summaries)
    total_cold = sum(item["cold_rows"] for item in rank_summaries)
    total_rows_by_rank = [item["total_rows"] for item in rank_summaries]
    hot_rows_by_rank = [item["hot_rows"] for item in rank_summaries]
    cold_rows_by_rank = [item["cold_rows"] for item in rank_summaries]

    return {
        "route_start_index": window["route_start_index"],
        "route_window_size": window["route_window_size"],
        "assignments": len(assignments),
        "tokens": len({item["token_row"] for item in assignments}),
        "top_k": max((item["topk_slot"] for item in assignments), default=-1) + 1,
        "hot_rows": total_hot,
        "cold_rows": total_cold,
        "hot_coverage": total_hot / len(assignments) if assignments else 0.0,
        "total_rows_by_rank": total_rows_by_rank,
        "hot_rows_by_rank": hot_rows_by_rank,
        "cold_rows_by_rank": cold_rows_by_rank,
        "max_total_rows_by_rank": max(total_rows_by_rank) if total_rows_by_rank else 0,
        "min_total_rows_by_rank": min(total_rows_by_rank) if total_rows_by_rank else 0,
        "imbalance_max_over_mean": (
            max(total_rows_by_rank) / mean([float(v) for v in total_rows_by_rank])
            if total_rows_by_rank else 0.0
        ),
        "rank_summaries": rank_summaries,
        "gather_map": gather_map if include_rows else None,
        "cold_owner_map": cold_owners if include_rows else None,
    }


def aggregate_window_plans(windows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "windows": len(windows),
        "assignments": summarize([float(item["assignments"]) for item in windows]),
        "hot_coverage": summarize([float(item["hot_coverage"]) for item in windows]),
        "cold_rows": summarize([float(item["cold_rows"]) for item in windows]),
        "max_total_rows_by_rank": summarize([
            float(item["max_total_rows_by_rank"]) for item in windows
        ]),
        "imbalance_max_over_mean": summarize([
            float(item["imbalance_max_over_mean"]) for item in windows
        ]),
    }


def write_markdown(path: str, result: dict[str, Any]) -> None:
    lines = []
    lines.append("# Qwen3.6 Hot-Replicated Route Work Queue Plan")
    lines.append("")
    lines.append(f"Input: `{result['metadata']['route_jsonl']}`")
    lines.append(f"Layer filter: `{result['metadata']['layer_regex']}`")
    lines.append(f"Hotset size: `{len(result['hotset']['experts'])}`")
    lines.append(f"Ranks: `{result['metadata']['ranks']}`")
    lines.append("")
    summary = result["summary"]
    lines.append("## Summary")
    lines.append("")
    lines.append(
        f"- Windows: `{summary['windows']}`; assignments/window mean "
        f"`{summary['assignments']['mean']:.1f}`."
    )
    lines.append(
        f"- Hot coverage mean/p95/min: `{summary['hot_coverage']['mean']:.3f}` / "
        f"`{summary['hot_coverage']['p95']:.3f}` / "
        f"`{summary['hot_coverage']['min']:.3f}`."
    )
    lines.append(
        f"- Cold rows mean/max: `{summary['cold_rows']['mean']:.1f}` / "
        f"`{summary['cold_rows']['max']:.1f}`."
    )
    lines.append(
        f"- Per-rank max rows mean/p95/max: "
        f"`{summary['max_total_rows_by_rank']['mean']:.1f}` / "
        f"`{summary['max_total_rows_by_rank']['p95']:.1f}` / "
        f"`{summary['max_total_rows_by_rank']['max']:.1f}`."
    )
    lines.append(
        f"- Imbalance max/mean mean/p95/max: "
        f"`{summary['imbalance_max_over_mean']['mean']:.3f}` / "
        f"`{summary['imbalance_max_over_mean']['p95']:.3f}` / "
        f"`{summary['imbalance_max_over_mean']['max']:.3f}`."
    )
    lines.append("")
    lines.append("## Windows")
    lines.append("")
    lines.append("| start | hot coverage | hot rows | cold rows | rows by rank | imbalance |")
    lines.append("|---:|---:|---:|---:|---|---:|")
    for window in result["windows"]:
        lines.append(
            f"| {window['route_start_index']} | {window['hot_coverage']:.3f} | "
            f"{window['hot_rows']} | {window['cold_rows']} | "
            f"`{window['total_rows_by_rank']}` | "
            f"{window['imbalance_max_over_mean']:.3f} |"
        )
    lines.append("")
    lines.append("## Decision")
    lines.append("")
    lines.append(
        "- The route metadata can be represented exactly as per-rank hot/cold "
        "queues plus a gather map; no expert dropping or approximate routing is "
        "required."
    )
    lines.append(
        "- This is still metadata only. A speed claim requires a one-launch "
        "kernel path that consumes these queues and proves exact output parity "
        "against `xpu_fused_moe` on the same windows."
    )
    lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route-jsonl", required=True)
    parser.add_argument("--route-layer-regex", required=True)
    parser.add_argument("--route-stage-regex", default="quark_int8_apply")
    parser.add_argument("--route-start-indices", type=parse_int_list, required=True)
    parser.add_argument("--route-window-size", type=int, default=16)
    parser.add_argument("--hotset-experts", type=parse_int_list)
    parser.add_argument("--hotset-size", type=int, default=64)
    parser.add_argument("--ranks", type=int, default=4)
    parser.add_argument("--include-rows", action="store_true")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--markdown-out")
    args = parser.parse_args()

    records, metadata = load_records(
        args.route_jsonl,
        layer_regex=args.route_layer_regex,
        stage_regex=args.route_stage_regex,
    )
    layer_counts = aggregate_counts(records)
    hotset = (
        validate_hotset(args.hotset_experts, len(layer_counts))
        if args.hotset_experts else hotset_from_counts(layer_counts, args.hotset_size)
    )
    windows = select_windows(
        records,
        start_indices=args.route_start_indices,
        window_size=args.route_window_size,
    )
    window_plans = [
        build_window_plan(
            window=window,
            layer_counts=layer_counts,
            hotset=hotset,
            ranks=args.ranks,
            include_rows=args.include_rows,
        )
        for window in windows
    ]
    result = {
        "metadata": {
            **metadata,
            "layer_regex": args.route_layer_regex,
            "stage_regex": args.route_stage_regex,
            "route_start_indices": args.route_start_indices,
            "route_window_size": args.route_window_size,
            "ranks": args.ranks,
            "include_rows": args.include_rows,
        },
        "hotset": {
            "experts": hotset,
            "size": len(hotset),
        },
        "summary": aggregate_window_plans(window_plans),
        "windows": window_plans,
    }
    Path(args.output_json).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.markdown_out:
        write_markdown(args.markdown_out, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
