#!/usr/bin/env python3
"""Summarize opt-in vLLM MoE route capture JSONL files.

The capture hook records logical top-k expert histograms per routed MoE call.
This script aggregates those records into layer-level distributions that can be
used to build shape-exact grouped-GEMM and persistent-MoE microbenchmarks.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (pct / 100.0) * (len(ordered) - 1)
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return float(ordered[lo])
    frac = rank - lo
    return float(ordered[lo] * (1.0 - frac) + ordered[hi] * frac)


def top_items(counts: list[int], limit: int) -> list[dict[str, int]]:
    ranked = sorted(enumerate(counts), key=lambda item: item[1], reverse=True)
    return [
        {"expert": int(expert), "count": int(count)}
        for expert, count in ranked[:limit]
        if count > 0
    ]


def expand_inputs(patterns: list[str]) -> list[str]:
    out: list[str] = []
    for pattern in patterns:
        matches = sorted(glob.glob(pattern))
        if matches:
            out.extend(matches)
        else:
            out.append(pattern)
    seen = set()
    deduped = []
    for path in out:
        if path not in seen:
            seen.add(path)
            deduped.append(path)
    return deduped


def load_records(paths: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        with open(path, "r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path}:{line_number}: invalid JSONL") from exc
                record["_source"] = path
                records.append(record)
    return records


def filter_records(
    records: list[dict[str, Any]],
    *,
    stage_regex: str | None,
    layer_regex: str | None,
    min_num_tokens: int | None,
    max_num_tokens: int | None,
) -> list[dict[str, Any]]:
    stage_pattern = re.compile(stage_regex) if stage_regex else None
    layer_pattern = re.compile(layer_regex) if layer_regex else None
    filtered: list[dict[str, Any]] = []
    for record in records:
        if stage_pattern and not stage_pattern.search(str(record.get("stage") or "")):
            continue
        if layer_pattern and not layer_pattern.search(str(record.get("layer") or "")):
            continue
        num_tokens = int(record.get("num_tokens") or 0)
        if min_num_tokens is not None and num_tokens < min_num_tokens:
            continue
        if max_num_tokens is not None and num_tokens > max_num_tokens:
            continue
        filtered.append(record)
    return filtered


def summarize_layer(records: list[dict[str, Any]], topn: int) -> dict[str, Any]:
    first = records[0]
    num_experts = int(first.get("num_experts") or len(first.get("counts", [])))
    total_counts = [0] * num_experts
    max_rows = []
    nonzero = []
    num_tokens = []
    assignments = []
    shapes = defaultdict(int)
    stages = defaultdict(int)
    topk_tuples = defaultdict(int)
    pids = set()
    ranks = set()

    for record in records:
        counts = record.get("counts") or []
        if len(counts) != num_experts:
            raise ValueError(
                f"record for {first.get('layer')} has {len(counts)} counts, "
                f"expected {num_experts}"
            )
        for idx, count in enumerate(counts):
            total_counts[idx] += int(count)
        max_rows.append(float(record.get("max_rows_per_expert", 0)))
        nonzero.append(float(record.get("nonzero_experts", 0)))
        num_tokens.append(float(record.get("num_tokens", 0)))
        assignments.append(float(record.get("assignments", 0)))
        shapes[tuple(record.get("shape", []))] += 1
        stages[str(record.get("stage") or "unknown")] += 1
        topk_ids = record.get("topk_ids")
        if isinstance(topk_ids, list):
            for row in topk_ids:
                if isinstance(row, list):
                    topk_tuples[tuple(int(item) for item in row)] += 1
        if record.get("pid") is not None:
            pids.add(str(record.get("pid")))
        if record.get("rank") is not None:
            ranks.add(str(record.get("rank")))

    active_counts = [count for count in total_counts if count > 0]
    total_assignments = int(sum(total_counts))
    return {
        "records": len(records),
        "pids": sorted(pids),
        "ranks": sorted(ranks),
        "top_k": int(first.get("top_k", 0)),
        "num_experts": num_experts,
        "total_tokens": int(sum(num_tokens)),
        "total_assignments": total_assignments,
        "unique_shapes": [
            {"shape": list(shape), "records": count}
            for shape, count in sorted(shapes.items(), key=lambda item: item[0])
        ],
        "stages": dict(sorted(stages.items())),
        "topk_tuples": [
            {"topk_ids": list(ids), "count": int(count)}
            for ids, count in sorted(
                topk_tuples.items(), key=lambda item: item[1], reverse=True
            )[:topn]
        ],
        "active_experts_total": len(active_counts),
        "aggregate_max_expert_share": (
            max(total_counts) / total_assignments if total_assignments else 0.0
        ),
        "aggregate_nonzero_expert_share": (
            len(active_counts) / num_experts if num_experts else 0.0
        ),
        "per_call_max_rows_per_expert": {
            "p50": percentile(max_rows, 50),
            "p90": percentile(max_rows, 90),
            "p95": percentile(max_rows, 95),
            "p99": percentile(max_rows, 99),
            "max": max(max_rows) if max_rows else 0.0,
        },
        "per_call_nonzero_experts": {
            "p50": percentile(nonzero, 50),
            "p90": percentile(nonzero, 90),
            "p95": percentile(nonzero, 95),
            "p99": percentile(nonzero, 99),
            "max": max(nonzero) if nonzero else 0.0,
        },
        "per_call_num_tokens": {
            "p50": percentile(num_tokens, 50),
            "p90": percentile(num_tokens, 90),
            "p95": percentile(num_tokens, 95),
            "p99": percentile(num_tokens, 99),
            "max": max(num_tokens) if num_tokens else 0.0,
        },
        "top_experts": top_items(total_counts, topn),
        "aggregate_counts": total_counts,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "inputs",
        nargs="+",
        help="JSONL files or glob patterns, for example /tmp/qwen36-routes-*.jsonl",
    )
    parser.add_argument("--out", help="Write summary JSON to this path")
    parser.add_argument("--topn", type=int, default=16)
    parser.add_argument(
        "--stage-regex",
        help="Only summarize records whose stage matches this regex",
    )
    parser.add_argument(
        "--layer-regex",
        help="Only summarize records whose layer matches this regex",
    )
    parser.add_argument(
        "--min-num-tokens",
        type=int,
        help="Only summarize records with at least this many routed tokens",
    )
    parser.add_argument(
        "--max-num-tokens",
        type=int,
        help="Only summarize records with at most this many routed tokens",
    )
    args = parser.parse_args()

    paths = expand_inputs(args.inputs)
    records_loaded = load_records(paths)
    records = filter_records(
        records_loaded,
        stage_regex=args.stage_regex,
        layer_regex=args.layer_regex,
        min_num_tokens=args.min_num_tokens,
        max_num_tokens=args.max_num_tokens,
    )
    by_layer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        layer = str(record.get("layer") or "unknown")
        by_layer[layer].append(record)

    layer_summaries = {
        layer: summarize_layer(layer_records, args.topn)
        for layer, layer_records in sorted(by_layer.items())
    }
    global_counts: list[int] = []
    global_stages: dict[str, int] = defaultdict(int)
    for layer_summary in layer_summaries.values():
        counts = layer_summary["aggregate_counts"]
        if not global_counts:
            global_counts = [0] * len(counts)
        for idx, count in enumerate(counts):
            global_counts[idx] += int(count)
        for stage, count in layer_summary.get("stages", {}).items():
            global_stages[str(stage)] += int(count)
    total_assignments = sum(global_counts)

    summary = {
        "input_files": paths,
        "filters": {
            "stage_regex": args.stage_regex,
            "layer_regex": args.layer_regex,
            "min_num_tokens": args.min_num_tokens,
            "max_num_tokens": args.max_num_tokens,
        },
        "records_loaded": len(records_loaded),
        "records": len(records),
        "layers": layer_summaries,
        "global": {
            "layers": len(layer_summaries),
            "total_assignments": int(total_assignments),
            "stages": dict(sorted(global_stages.items())),
            "top_experts": top_items(global_counts, args.topn),
            "aggregate_counts": global_counts,
        },
    }

    text = json.dumps(summary, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
