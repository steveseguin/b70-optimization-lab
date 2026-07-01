#!/usr/bin/env python3
"""Summarize Qwen3.6 MoE route JSONL into kernel flight records.

This is a CPU-only companion to the XPU route-replay benchmarks. It turns real
captured top-k routes into layer/window summaries that can guide persistent MoE,
expert-parallel, hot-expert replication, and tile-native W8A8 repack work.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    pos = (len(ordered) - 1) * pct
    lo = math.floor(pos)
    hi = min(lo + 1, len(ordered) - 1)
    frac = pos - lo
    return float(ordered[lo] * (1.0 - frac) + ordered[hi] * frac)


def stats(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "p50": None, "p90": None, "p99": None, "max": None}
    return {
        "mean": float(sum(values) / len(values)),
        "p50": percentile(values, 0.50),
        "p90": percentile(values, 0.90),
        "p99": percentile(values, 0.99),
        "max": float(max(values)),
    }


def parse_csv_ints(value: str) -> list[int]:
    out = []
    for item in value.split(","):
        item = item.strip()
        if item:
            out.append(int(item))
    if not out:
        raise argparse.ArgumentTypeError("expected at least one integer")
    return out


def expand_inputs(patterns: list[str]) -> list[str]:
    paths: list[str] = []
    for pattern in patterns:
        matches = sorted(glob.glob(pattern))
        paths.extend(matches or [pattern])
    seen = set()
    deduped = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            deduped.append(path)
    return deduped


def layer_index(layer: str) -> int | None:
    match = re.search(r"\.layers\.(\d+)\.", layer)
    if not match:
        return None
    return int(match.group(1))


def load_records(args: argparse.Namespace) -> list[dict[str, Any]]:
    stage_re = re.compile(args.stage_regex) if args.stage_regex else None
    layer_re = re.compile(args.layer_regex) if args.layer_regex else None
    records = []
    for path in expand_inputs(args.inputs):
        with open(path, "r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                record["_source"] = path
                record["_line"] = line_number
                stage = str(record.get("stage") or "")
                layer = str(record.get("layer") or "")
                if stage_re and not stage_re.search(stage):
                    continue
                if layer_re and not layer_re.search(layer):
                    continue
                num_tokens = int(record.get("num_tokens") or 0)
                if args.min_num_tokens is not None and num_tokens < args.min_num_tokens:
                    continue
                if args.max_num_tokens is not None and num_tokens > args.max_num_tokens:
                    continue
                topk_ids = record.get("topk_ids")
                if args.require_topk_ids and not isinstance(topk_ids, list):
                    continue
                records.append(record)
    if not records:
        raise SystemExit("no route records matched filters")
    records.sort(
        key=lambda row: (
            str(row.get("layer") or ""),
            int(row.get("call") or 0),
            float(row.get("ts") or 0.0),
            int(row.get("_line") or 0),
        )
    )
    return records


def top_items(counter: Counter[int], limit: int) -> list[dict[str, int]]:
    return [
        {"expert": int(expert), "count": int(count)}
        for expert, count in counter.most_common(limit)
    ]


def counter_share(counter: Counter[int], hot_size: int) -> float:
    total = sum(counter.values())
    if not total:
        return 0.0
    return sum(count for _expert, count in counter.most_common(hot_size)) / total


def tuple_summary(records: list[dict[str, Any]], topn: int) -> dict[str, Any]:
    tuples: Counter[tuple[int, ...]] = Counter()
    total = 0
    for record in records:
        topk_ids = record.get("topk_ids")
        if not isinstance(topk_ids, list):
            continue
        for row in topk_ids:
            if isinstance(row, list):
                tuples[tuple(int(item) for item in row)] += 1
                total += 1
    top = [
        {"topk_ids": list(ids), "count": int(count)}
        for ids, count in tuples.most_common(topn)
    ]
    return {
        "total_rows": total,
        "unique_tuples": len(tuples),
        "top_tuple_share": (top[0]["count"] / total) if total and top else 0.0,
        "top_tuples": top,
    }


def summarize_window(
    records: list[dict[str, Any]],
    *,
    hot_sizes: list[int],
    topn: int,
) -> dict[str, Any]:
    expert_counts: Counter[int] = Counter()
    max_rows = []
    nonzero = []
    num_tokens = []
    for record in records:
        counts = record.get("counts") or []
        for expert, count in enumerate(counts):
            if count:
                expert_counts[int(expert)] += int(count)
        max_rows.append(float(record.get("max_rows_per_expert") or 0))
        nonzero.append(float(record.get("nonzero_experts") or 0))
        num_tokens.append(float(record.get("num_tokens") or 0))
    total_assignments = sum(expert_counts.values())
    hot_coverage = {
        str(size): counter_share(expert_counts, size) for size in hot_sizes
    }
    return {
        "records": len(records),
        "call_start": int(records[0].get("call") or 0) if records else None,
        "call_end": int(records[-1].get("call") or 0) if records else None,
        "total_tokens": int(sum(num_tokens)),
        "total_assignments": int(total_assignments),
        "active_experts": len(expert_counts),
        "hot_coverage": hot_coverage,
        "max_rows_per_expert": stats(max_rows),
        "nonzero_experts_per_call": stats(nonzero),
        "num_tokens_per_call": stats(num_tokens),
        "top_experts": top_items(expert_counts, topn),
        "topk_tuple_summary": tuple_summary(records, topn),
    }


def summarize_layer(
    layer: str,
    records: list[dict[str, Any]],
    *,
    window_size: int,
    hot_sizes: list[int],
    topn: int,
) -> dict[str, Any]:
    aggregate = summarize_window(records, hot_sizes=hot_sizes, topn=topn)
    windows = []
    for start in range(0, len(records), window_size):
        chunk = records[start:start + window_size]
        if chunk:
            windows.append(summarize_window(chunk, hot_sizes=hot_sizes, topn=topn))

    window_hot: dict[str, list[float]] = defaultdict(list)
    window_active = []
    window_top_tuple = []
    for window in windows:
        window_active.append(float(window["active_experts"]))
        window_top_tuple.append(
            float(window["topk_tuple_summary"].get("top_tuple_share") or 0.0)
        )
        for size, share in window["hot_coverage"].items():
            window_hot[size].append(float(share))

    records_per_call_shape: Counter[str] = Counter()
    stages: Counter[str] = Counter()
    sources: Counter[str] = Counter()
    for record in records:
        records_per_call_shape[str(record.get("shape") or [])] += 1
        stages[str(record.get("stage") or "unknown")] += 1
        sources[str(record.get("_source") or "")] += 1

    return {
        "layer": layer,
        "layer_index": layer_index(layer),
        "stages": dict(sorted(stages.items())),
        "sources": dict(sorted(sources.items())),
        "shapes": dict(sorted(records_per_call_shape.items())),
        "aggregate": aggregate,
        "window_size": window_size,
        "window_count": len(windows),
        "window_active_experts": stats(window_active),
        "window_top_tuple_share": stats(window_top_tuple),
        "window_hot_coverage": {
            size: stats(values) for size, values in sorted(window_hot.items())
        },
        "windows": windows,
    }


def make_markdown(summary: dict[str, Any], top_layers: list[dict[str, Any]]) -> str:
    lines = [
        "# Qwen3.6 MoE Flight Record",
        "",
        f"Inputs: `{', '.join(summary['input_files'])}`",
        f"Records: `{summary['records']}`",
        f"Window size: `{summary['window_size']}`",
        "",
        "## Ranked Layers",
        "",
        "| rank | layer | records | active experts | top16 coverage | top32 coverage | p50 window active | p50 top tuple |",
        "|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for idx, layer in enumerate(top_layers, start=1):
        aggregate = layer["aggregate"]
        hot = aggregate["hot_coverage"]
        window_active = layer["window_active_experts"]
        tuple_stats = layer["window_top_tuple_share"]
        lines.append(
            "| "
            f"{idx} | `{layer['layer']}` | {aggregate['records']} | "
            f"{aggregate['active_experts']} | "
            f"{hot.get('16', 0.0):.3f} | {hot.get('32', 0.0):.3f} | "
            f"{(window_active.get('p50') or 0.0):.1f} | "
            f"{(tuple_stats.get('p50') or 0.0):.3f} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Higher hot coverage means hot-expert replication or tile-native repack has more chance to help.",
            "- Lower window active experts means a persistent worker scheduler has less imbalance to solve.",
            "- High top tuple share means repeated exact top-k routes, useful for route-window replay fixtures.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", help="Route JSONL files or globs")
    parser.add_argument("--out", required=True, help="Write summary JSON")
    parser.add_argument("--markdown-out", help="Optional Markdown summary")
    parser.add_argument("--stage-regex", default="^quark_int8_apply$")
    parser.add_argument("--layer-regex")
    parser.add_argument("--min-num-tokens", type=int, default=1)
    parser.add_argument("--max-num-tokens", type=int, default=1)
    parser.add_argument("--window-size", type=int, default=16)
    parser.add_argument("--hot-sizes", type=parse_csv_ints, default=parse_csv_ints("8,16,32,64"))
    parser.add_argument("--topn", type=int, default=16)
    parser.add_argument("--require-topk-ids", action="store_true")
    args = parser.parse_args()

    input_files = expand_inputs(args.inputs)
    records = load_records(args)
    by_layer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_layer[str(record.get("layer") or "unknown")].append(record)

    layers = [
        summarize_layer(
            layer,
            layer_records,
            window_size=args.window_size,
            hot_sizes=args.hot_sizes,
            topn=args.topn,
        )
        for layer, layer_records in sorted(by_layer.items(), key=lambda item: layer_index(item[0]) or 9999)
    ]

    def priority(layer: dict[str, Any]) -> tuple[float, float, float]:
        aggregate = layer["aggregate"]
        hot16 = float(aggregate["hot_coverage"].get("16", 0.0))
        active = float(aggregate["active_experts"] or 1)
        records_count = float(aggregate["records"] or 0)
        tuple_share = float(layer["window_top_tuple_share"].get("p50") or 0.0)
        return (hot16, tuple_share, records_count / active)

    ranked_layers = sorted(layers, key=priority, reverse=True)
    summary = {
        "input_files": input_files,
        "filters": {
            "stage_regex": args.stage_regex,
            "layer_regex": args.layer_regex,
            "min_num_tokens": args.min_num_tokens,
            "max_num_tokens": args.max_num_tokens,
            "require_topk_ids": args.require_topk_ids,
        },
        "window_size": args.window_size,
        "hot_sizes": args.hot_sizes,
        "records": len(records),
        "layer_count": len(layers),
        "ranked_layer_names": [layer["layer"] for layer in ranked_layers],
        "layers": {layer["layer"]: layer for layer in layers},
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    if args.markdown_out:
        md = Path(args.markdown_out)
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text(make_markdown(summary, ranked_layers[:16]))
    print(json.dumps({"out": str(out), "records": len(records), "layers": len(layers)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
