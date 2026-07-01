#!/usr/bin/env python3
"""Build layer/prompt heatmaps from Qwen3.6 MoE route captures.

The route-capture summarizer is useful for one capture file. This script is a
next-step planner: it accepts multiple labeled capture summaries or JSONL files
and ranks layers by route locality/skew. Higher skew/locality is where
layer-specific expert packing, grouped-GEMM policy, or persistent-MoE work is
most likely to pay off without changing model math.
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


LAYER_RE = re.compile(r"layers\.(\d+)\.")


def parse_labeled_input(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError(
            "inputs must be LABEL=PATH_OR_GLOB, for example natural=/tmp/routes-*.jsonl"
        )
    label, pattern = value.split("=", 1)
    label = label.strip()
    pattern = pattern.strip()
    if not label:
        raise argparse.ArgumentTypeError("input label cannot be empty")
    if not pattern:
        raise argparse.ArgumentTypeError("input path/glob cannot be empty")
    return label, pattern


def expand(pattern: str) -> list[str]:
    matches = sorted(glob.glob(pattern))
    return matches if matches else [pattern]


def layer_index(layer: str) -> int | None:
    match = LAYER_RE.search(layer)
    return int(match.group(1)) if match else None


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    if len(values) == 1:
        return float(values[0])
    pos = (pct / 100.0) * (len(values) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return float(values[lo])
    frac = pos - lo
    return float(values[lo] * (1 - frac) + values[hi] * frac)


def entropy(counts: list[int]) -> float:
    total = sum(counts)
    if total <= 0:
        return 0.0
    out = 0.0
    for count in counts:
        if count <= 0:
            continue
        p = count / total
        out -= p * math.log(p)
    return out


def top_experts(counts: list[int], topn: int) -> list[dict[str, int]]:
    return [
        {"expert": int(expert), "count": int(count)}
        for expert, count in sorted(
            enumerate(counts), key=lambda item: item[1], reverse=True
        )[:topn]
        if count > 0
    ]


def summarize_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_layer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_layer[str(record.get("layer") or "unknown")].append(record)

    summaries: dict[str, dict[str, Any]] = {}
    for layer, layer_records in by_layer.items():
        first = layer_records[0]
        num_experts = int(first.get("num_experts") or len(first.get("counts", [])))
        counts = [0] * num_experts
        max_rows = []
        nonzero = []
        num_tokens = []
        stages: Counter[str] = Counter()
        topk_tuples: Counter[tuple[int, ...]] = Counter()
        for record in layer_records:
            row_counts = record.get("counts") or []
            if len(row_counts) != num_experts:
                raise ValueError(
                    f"{layer}: expected {num_experts} counts, got {len(row_counts)}"
                )
            for idx, count in enumerate(row_counts):
                counts[idx] += int(count)
            max_rows.append(float(record.get("max_rows_per_expert", 0)))
            nonzero.append(float(record.get("nonzero_experts", 0)))
            num_tokens.append(float(record.get("num_tokens", 0)))
            stages[str(record.get("stage") or "unknown")] += 1
            topk_ids = record.get("topk_ids")
            if isinstance(topk_ids, list):
                for row in topk_ids:
                    if isinstance(row, list):
                        topk_tuples[tuple(int(item) for item in row)] += 1

        summaries[layer] = {
            "records": len(layer_records),
            "top_k": int(first.get("top_k", 0)),
            "num_experts": num_experts,
            "total_tokens": int(sum(num_tokens)),
            "total_assignments": int(sum(counts)),
            "aggregate_counts": counts,
            "stages": dict(sorted(stages.items())),
            "per_call_nonzero_experts": {
                "p50": percentile(nonzero, 50),
                "p90": percentile(nonzero, 90),
                "max": max(nonzero) if nonzero else 0.0,
            },
            "per_call_max_rows_per_expert": {
                "p50": percentile(max_rows, 50),
                "p90": percentile(max_rows, 90),
                "max": max(max_rows) if max_rows else 0.0,
            },
            "topk_tuples": [
                {"topk_ids": list(ids), "count": int(count)}
                for ids, count in topk_tuples.most_common(32)
            ],
        }
    return summaries


def load_jsonl_summary(
    paths: list[str],
    *,
    stage_regex: str | None,
    layer_regex: str | None,
    min_num_tokens: int | None,
    max_num_tokens: int | None,
) -> dict[str, dict[str, Any]]:
    stage_pattern = re.compile(stage_regex) if stage_regex else None
    layer_pattern = re.compile(layer_regex) if layer_regex else None
    records = []
    for path in paths:
        with Path(path).open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                layer = str(record.get("layer") or "")
                stage = str(record.get("stage") or "")
                if layer_pattern and not layer_pattern.search(layer):
                    continue
                if stage_pattern and not stage_pattern.search(stage):
                    continue
                num_tokens = int(record.get("num_tokens") or 0)
                if min_num_tokens is not None and num_tokens < min_num_tokens:
                    continue
                if max_num_tokens is not None and num_tokens > max_num_tokens:
                    continue
                record["_source"] = f"{path}:{line_number}"
                records.append(record)
    return summarize_records(records)


def load_summary_or_jsonl(
    paths: list[str],
    *,
    stage_regex: str | None,
    layer_regex: str | None,
    min_num_tokens: int | None,
    max_num_tokens: int | None,
) -> dict[str, dict[str, Any]]:
    if len(paths) == 1 and paths[0].endswith(".json"):
        data = json.loads(Path(paths[0]).read_text(encoding="utf-8"))
        layers = data.get("layers")
        if isinstance(layers, dict):
            layer_pattern = re.compile(layer_regex) if layer_regex else None
            out: dict[str, dict[str, Any]] = {}
            for layer, summary in layers.items():
                if layer_pattern and not layer_pattern.search(layer):
                    continue
                out[layer] = summary
            return out
    return load_jsonl_summary(
        paths,
        stage_regex=stage_regex,
        layer_regex=layer_regex,
        min_num_tokens=min_num_tokens,
        max_num_tokens=max_num_tokens,
    )


def layer_metric(label: str, layer: str, summary: dict[str, Any], topn: int) -> dict[str, Any]:
    counts = [int(item) for item in summary.get("aggregate_counts") or []]
    total = sum(counts)
    num_experts = int(summary.get("num_experts") or len(counts) or 0)
    active = sum(1 for item in counts if item > 0)
    topn_share = (
        sum(sorted(counts, reverse=True)[:topn]) / total if total else 0.0
    )
    top8_share = sum(sorted(counts, reverse=True)[:8]) / total if total else 0.0
    max_share = max(counts) / total if total and counts else 0.0
    active_share = active / num_experts if num_experts else 0.0
    ent = entropy(counts)
    uniform_topn_share = min(topn, num_experts) / num_experts if num_experts else 0.0
    skew_over_uniform = topn_share - uniform_topn_share
    normalized_entropy_all = ent / math.log(num_experts) if num_experts > 1 else 0.0
    normalized_entropy_active = ent / math.log(active) if active > 1 else 0.0
    top_expert_rows = top_experts(counts, topn)
    return {
        "label": label,
        "layer": layer,
        "layer_index": layer_index(layer),
        "records": int(summary.get("records") or 0),
        "stages": summary.get("stages") or {},
        "top_k": int(summary.get("top_k") or 0),
        "num_experts": num_experts,
        "total_tokens": int(summary.get("total_tokens") or 0),
        "total_assignments": int(summary.get("total_assignments") or total),
        "active_experts_total": active,
        "active_expert_share": active_share,
        "max_expert_share": max_share,
        "top8_share": top8_share,
        "topn": topn,
        "topn_share": topn_share,
        "uniform_topn_share": uniform_topn_share,
        "skew_over_uniform": skew_over_uniform,
        "normalized_entropy_all_experts": normalized_entropy_all,
        "normalized_entropy_active_experts": normalized_entropy_active,
        "priority_score": skew_over_uniform * math.log1p(total),
        "top_experts": top_expert_rows,
        "top_expert_ids": [item["expert"] for item in top_expert_rows],
        "per_call_nonzero_experts": summary.get("per_call_nonzero_experts") or {},
        "per_call_max_rows_per_expert": summary.get("per_call_max_rows_per_expert") or {},
        "topk_tuples": summary.get("topk_tuples") or [],
    }


def layer_sort_key(layer: str) -> tuple[int, str]:
    idx = layer_index(layer)
    return (idx if idx is not None else 10_000, layer)


def build_heatmap(
    labeled_inputs: list[tuple[str, str]],
    *,
    topn: int,
    stage_regex: str | None,
    layer_regex: str | None,
    min_num_tokens: int | None,
    max_num_tokens: int | None,
) -> dict[str, Any]:
    labels: dict[str, dict[str, Any]] = {}
    by_layer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for label, pattern in labeled_inputs:
        paths = expand(pattern)
        summaries = load_summary_or_jsonl(
            paths,
            stage_regex=stage_regex,
            layer_regex=layer_regex,
            min_num_tokens=min_num_tokens,
            max_num_tokens=max_num_tokens,
        )
        metrics = [
            layer_metric(label, layer, summary, topn)
            for layer, summary in sorted(summaries.items(), key=lambda item: layer_sort_key(item[0]))
        ]
        for item in metrics:
            by_layer[item["layer"]].append(item)
        labels[label] = {
            "input_pattern": pattern,
            "input_files": paths,
            "layers": {item["layer"]: item for item in metrics},
            "ranked_layers": sorted(metrics, key=lambda item: item["priority_score"], reverse=True),
        }

    ranked_layers = []
    for layer, items in by_layer.items():
        label_count = len(items)
        mean_priority = sum(item["priority_score"] for item in items) / label_count
        mean_topn_share = sum(item["topn_share"] for item in items) / label_count
        mean_max_share = sum(item["max_expert_share"] for item in items) / label_count
        mean_active_share = sum(item["active_expert_share"] for item in items) / label_count
        top_sets = [set(item["top_expert_ids"][:topn]) for item in items if item["top_expert_ids"]]
        if len(top_sets) > 1:
            intersection = set.intersection(*top_sets)
            union = set.union(*top_sets)
            topn_jaccard_all_labels = len(intersection) / len(union) if union else 0.0
        else:
            topn_jaccard_all_labels = 1.0 if top_sets else 0.0
        ranked_layers.append({
            "layer": layer,
            "layer_index": layer_index(layer),
            "labels": [item["label"] for item in items],
            "label_count": label_count,
            "mean_priority_score": mean_priority,
            "mean_topn_share": mean_topn_share,
            "mean_max_expert_share": mean_max_share,
            "mean_active_expert_share": mean_active_share,
            "topn_jaccard_all_labels": topn_jaccard_all_labels,
            "items": items,
        })

    ranked_layers.sort(
        key=lambda item: (
            item["mean_priority_score"],
            item["mean_topn_share"],
            -item["mean_active_expert_share"],
        ),
        reverse=True,
    )
    return {
        "inputs": [
            {"label": label, "pattern": pattern, "files": expand(pattern)}
            for label, pattern in labeled_inputs
        ],
        "filters": {
            "stage_regex": stage_regex,
            "layer_regex": layer_regex,
            "min_num_tokens": min_num_tokens,
            "max_num_tokens": max_num_tokens,
        },
        "topn": topn,
        "labels": labels,
        "ranked_layers": ranked_layers,
    }


def print_table(data: dict[str, Any], limit: int) -> None:
    print("rank layer labels priority topN_share max_share active_share topN_jaccard")
    for rank, layer in enumerate(data["ranked_layers"][:limit], start=1):
        print(
            f"{rank:>4} "
            f"{(layer['layer_index'] if layer['layer_index'] is not None else '?'):>5} "
            f"{','.join(layer['labels']):<24} "
            f"{layer['mean_priority_score']:.4f} "
            f"{layer['mean_topn_share']:.4f} "
            f"{layer['mean_max_expert_share']:.4f} "
            f"{layer['mean_active_expert_share']:.4f} "
            f"{layer['topn_jaccard_all_labels']:.4f}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        action="append",
        type=parse_labeled_input,
        required=True,
        help="Labeled JSON summary or JSONL/glob, for example decode=data/*summary.json",
    )
    parser.add_argument("--out", help="Write full heatmap JSON to this path")
    parser.add_argument("--topn", type=int, default=16)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--stage-regex")
    parser.add_argument("--layer-regex")
    parser.add_argument("--min-num-tokens", type=int)
    parser.add_argument("--max-num-tokens", type=int)
    args = parser.parse_args()

    heatmap = build_heatmap(
        args.input,
        topn=args.topn,
        stage_regex=args.stage_regex,
        layer_regex=args.layer_regex,
        min_num_tokens=args.min_num_tokens,
        max_num_tokens=args.max_num_tokens,
    )
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(heatmap, indent=2, sort_keys=True) + "\n")
    print_table(heatmap, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
