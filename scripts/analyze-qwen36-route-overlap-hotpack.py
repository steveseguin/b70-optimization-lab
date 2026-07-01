#!/usr/bin/env python3
"""Analyze Qwen3.6 MoE route overlap and hotpack coverage.

This consumes labeled route-capture JSONL files and answers the practical
question behind hot-expert work: would one global expert pack cover decode
traffic, or do we need route/prompt buckets?
"""

from __future__ import annotations

import argparse
import glob
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


LAYER_RE = re.compile(r"layers\.(\d+)\.")


def parse_labeled_input(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("expected LABEL=PATH_OR_GLOB")
    label, pattern = value.split("=", 1)
    label = label.strip()
    pattern = pattern.strip()
    if not label or not pattern:
        raise argparse.ArgumentTypeError("label and path/glob must be non-empty")
    return label, pattern


def expand(pattern: str) -> list[Path]:
    matches = sorted(glob.glob(pattern))
    return [Path(item) for item in (matches if matches else [pattern])]


def layer_index(layer: str) -> int | None:
    match = LAYER_RE.search(layer)
    return int(match.group(1)) if match else None


def top_ids(counts: list[int], k: int) -> list[int]:
    return [
        expert
        for expert, count in sorted(
            enumerate(counts), key=lambda item: item[1], reverse=True
        )[:k]
        if count > 0
    ]


def coverage(counts: list[int], ids: set[int]) -> float:
    total = sum(counts)
    if total <= 0:
        return 0.0
    return sum(counts[idx] for idx in ids if 0 <= idx < len(counts)) / total


def jaccard(left: set[int], right: set[int]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def add_counts(left: list[int], right: list[int]) -> list[int]:
    size = max(len(left), len(right))
    out = [0] * size
    for idx in range(size):
        out[idx] = (left[idx] if idx < len(left) else 0) + (
            right[idx] if idx < len(right) else 0
        )
    return out


def load_counts(
    inputs: list[tuple[str, str]],
    *,
    stage_regex: str | None,
    layer_regex: str | None,
    min_num_tokens: int | None,
    max_num_tokens: int | None,
) -> dict[str, dict[str, dict[str, Any]]]:
    stage_pattern = re.compile(stage_regex) if stage_regex else None
    layer_pattern = re.compile(layer_regex) if layer_regex else None
    out: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for label, pattern in inputs:
        for path in expand(pattern):
            with path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    record = json.loads(line)
                    layer = str(record.get("layer") or "unknown")
                    stage = str(record.get("stage") or "unknown")
                    if stage_pattern and not stage_pattern.search(stage):
                        continue
                    if layer_pattern and not layer_pattern.search(layer):
                        continue
                    num_tokens = int(record.get("num_tokens") or 0)
                    if min_num_tokens is not None and num_tokens < min_num_tokens:
                        continue
                    if max_num_tokens is not None and num_tokens > max_num_tokens:
                        continue
                    row_counts = [int(item) for item in record.get("counts") or []]
                    if not row_counts:
                        raise ValueError(f"{path}:{line_number} has no counts")
                    if layer not in out[label]:
                        out[label][layer] = {
                            "counts": [0] * len(row_counts),
                            "records": 0,
                            "tokens": 0,
                            "assignments": 0,
                        }
                    item = out[label][layer]
                    if len(item["counts"]) != len(row_counts):
                        raise ValueError(
                            f"{path}:{line_number} count width changed for {label}/{layer}"
                        )
                    item["counts"] = add_counts(item["counts"], row_counts)
                    item["records"] += 1
                    item["tokens"] += num_tokens
                    item["assignments"] += sum(row_counts)
    return {label: dict(layers) for label, layers in out.items()}


def partitions(items: tuple[str, ...], max_groups: int) -> list[tuple[tuple[str, ...], ...]]:
    """Return set partitions of items into at most max_groups groups."""
    if not items:
        return [()]
    first, *rest = items
    rest_partitions = partitions(tuple(rest), max_groups)
    out: list[tuple[tuple[str, ...], ...]] = []
    seen = set()
    for partition in rest_partitions:
        if len(partition) < max_groups:
            candidate = tuple(sorted(((first,),) + partition))
            key = tuple(candidate)
            if key not in seen:
                seen.add(key)
                out.append(candidate)
        for idx in range(len(partition)):
            merged = list(partition)
            merged[idx] = tuple(sorted((first,) + merged[idx]))
            candidate = tuple(sorted(merged))
            key = tuple(candidate)
            if key not in seen:
                seen.add(key)
                out.append(candidate)
    return out


def evaluate_partition(
    partition: tuple[tuple[str, ...], ...],
    layer_counts: dict[str, list[int]],
    hotpack_k: int,
) -> dict[str, Any]:
    total_assignments = sum(sum(counts) for counts in layer_counts.values())
    covered = 0.0
    groups = []
    for group in partition:
        group_counts: list[int] = []
        for label in group:
            group_counts = add_counts(group_counts, layer_counts[label])
        ids = set(top_ids(group_counts, hotpack_k))
        group_assignments = 0
        group_covered = 0.0
        for label in group:
            label_assignments = sum(layer_counts[label])
            label_covered = coverage(layer_counts[label], ids) * label_assignments
            group_assignments += label_assignments
            group_covered += label_covered
        covered += group_covered
        groups.append(
            {
                "labels": list(group),
                "hot_expert_ids": sorted(ids),
                "assignments": group_assignments,
                "coverage": group_covered / group_assignments
                if group_assignments
                else 0.0,
            }
        )
    return {
        "groups": groups,
        "coverage": covered / total_assignments if total_assignments else 0.0,
        "total_assignments": total_assignments,
        "group_count": len(partition),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", type=parse_labeled_input, required=True)
    parser.add_argument("--topn", type=int, default=16)
    parser.add_argument("--hotpack-k", action="append", type=int)
    parser.add_argument("--max-buckets", type=int, default=4)
    parser.add_argument("--stage-regex")
    parser.add_argument("--layer-regex")
    parser.add_argument("--min-num-tokens", type=int)
    parser.add_argument("--max-num-tokens", type=int)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-md", type=Path)
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()

    hotpack_ks = sorted(set(args.hotpack_k or [8, 16, 32, 64]))
    counts_by_label = load_counts(
        args.input,
        stage_regex=args.stage_regex,
        layer_regex=args.layer_regex,
        min_num_tokens=args.min_num_tokens,
        max_num_tokens=args.max_num_tokens,
    )
    labels = sorted(counts_by_label)
    layers = sorted(
        {layer for by_layer in counts_by_label.values() for layer in by_layer},
        key=lambda layer: (layer_index(layer) is None, layer_index(layer) or 0, layer),
    )

    layer_results = []
    for layer in layers:
        layer_counts = {
            label: counts_by_label[label][layer]["counts"]
            for label in labels
            if layer in counts_by_label[label]
            and sum(counts_by_label[label][layer]["counts"]) > 0
        }
        if not layer_counts:
            continue
        layer_labels = tuple(sorted(layer_counts))
        top_sets = {
            label: set(top_ids(layer_counts[label], args.topn))
            for label in layer_labels
        }
        pairwise = []
        for i, left in enumerate(layer_labels):
            for right in layer_labels[i + 1 :]:
                pairwise.append(
                    {
                        "left": left,
                        "right": right,
                        "jaccard": jaccard(top_sets[left], top_sets[right]),
                        "intersection": sorted(top_sets[left] & top_sets[right]),
                        "union_size": len(top_sets[left] | top_sets[right]),
                    }
                )
        total_counts: list[int] = []
        for counts in layer_counts.values():
            total_counts = add_counts(total_counts, counts)
        total_assignments = sum(total_counts)
        global_hotpacks = {}
        label_specific = {}
        bucket_results = {}
        for hotpack_k in hotpack_ks:
            global_ids = set(top_ids(total_counts, hotpack_k))
            global_hotpacks[str(hotpack_k)] = {
                "expert_ids": sorted(global_ids),
                "weighted_coverage": sum(
                    coverage(counts, global_ids) * sum(counts)
                    for counts in layer_counts.values()
                )
                / total_assignments
                if total_assignments
                else 0.0,
                "coverage_by_label": {
                    label: coverage(counts, global_ids)
                    for label, counts in sorted(layer_counts.items())
                },
            }
            label_specific[str(hotpack_k)] = {
                "weighted_coverage": sum(
                    coverage(counts, set(top_ids(counts, hotpack_k))) * sum(counts)
                    for counts in layer_counts.values()
                )
                / total_assignments
                if total_assignments
                else 0.0,
                "coverage_by_label": {
                    label: coverage(counts, set(top_ids(counts, hotpack_k)))
                    for label, counts in sorted(layer_counts.items())
                },
            }
            candidates = []
            for partition in partitions(layer_labels, min(args.max_buckets, len(layer_labels))):
                candidates.append(evaluate_partition(partition, layer_counts, hotpack_k))
            candidates.sort(key=lambda item: (item["coverage"], -item["group_count"]), reverse=True)
            bucket_results[str(hotpack_k)] = candidates[: min(8, len(candidates))]
        mean_jaccard = (
            sum(item["jaccard"] for item in pairwise) / len(pairwise)
            if pairwise
            else 1.0
        )
        topn_union = set().union(*top_sets.values()) if top_sets else set()
        layer_results.append(
            {
                "layer": layer,
                "layer_index": layer_index(layer),
                "labels": list(layer_labels),
                "records_by_label": {
                    label: counts_by_label[label][layer]["records"]
                    for label in layer_labels
                },
                "assignments_by_label": {
                    label: sum(layer_counts[label]) for label in layer_labels
                },
                "total_assignments": total_assignments,
                "mean_pairwise_topn_jaccard": mean_jaccard,
                "topn_union_size": len(topn_union),
                "topn_intersection": sorted(set.intersection(*top_sets.values()))
                if top_sets
                else [],
                "pairwise_topn_jaccard": pairwise,
                "global_hotpacks": global_hotpacks,
                "label_specific_hotpacks": label_specific,
                "bucket_hotpacks": bucket_results,
            }
        )

    for item in layer_results:
        k = str(args.topn)
        global_cov = item["global_hotpacks"].get(k, {}).get("weighted_coverage", 0.0)
        label_cov = item["label_specific_hotpacks"].get(k, {}).get("weighted_coverage", 0.0)
        best_bucket = item["bucket_hotpacks"].get(k, [{}])[0].get("coverage", 0.0)
        item["priority_score"] = (
            (label_cov - global_cov)
            + max(0.0, best_bucket - global_cov)
            + (1.0 - item["mean_pairwise_topn_jaccard"]) * 0.25
        ) * item["total_assignments"]

    layer_results.sort(key=lambda item: item["priority_score"], reverse=True)
    out = {
        "topn": args.topn,
        "hotpack_ks": hotpack_ks,
        "labels": labels,
        "filters": {
            "stage_regex": args.stage_regex,
            "layer_regex": args.layer_regex,
            "min_num_tokens": args.min_num_tokens,
            "max_num_tokens": args.max_num_tokens,
        },
        "inputs": [{"label": label, "pattern": pattern} for label, pattern in args.input],
        "layers": layer_results,
    }
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")

    lines = [
        "# Qwen3.6 Route Overlap and Hotpack Simulation",
        "",
        f"Top-N set size: `{args.topn}`",
        f"Hotpack sizes: `{', '.join(str(item) for item in hotpack_ks)}`",
        "",
        "| Rank | Layer | Records | TopN union | TopN Jaccard | Global K=16 | Label K=16 | Best buckets K=16 | Read |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for rank, item in enumerate(layer_results[: args.limit], start=1):
        k = str(args.topn)
        records = sum(item["records_by_label"].values())
        global_cov = item["global_hotpacks"].get(k, {}).get("weighted_coverage", 0.0)
        label_cov = item["label_specific_hotpacks"].get(k, {}).get("weighted_coverage", 0.0)
        bucket_cov = item["bucket_hotpacks"].get(k, [{}])[0].get("coverage", 0.0)
        read = "bucket/dynamic" if bucket_cov - global_cov >= 0.05 else "global-ok"
        lines.append(
            f"| {rank} | {item['layer_index']} | {records} | {item['topn_union_size']} | "
            f"{item['mean_pairwise_topn_jaccard']:.4f} | {global_cov:.4f} | "
            f"{label_cov:.4f} | {bucket_cov:.4f} | {read} |"
        )
    lines.append("")
    lines.append("## Best K=16 Bucket Assignments")
    lines.append("")
    for item in layer_results[: args.limit]:
        k = str(args.topn)
        best = item["bucket_hotpacks"].get(k, [{}])[0]
        lines.append(f"### Layer {item['layer_index']}")
        lines.append("")
        lines.append(
            f"Global K=16 coverage: `{item['global_hotpacks'][k]['weighted_coverage']:.4f}`; "
            f"label-specific upper bound: `{item['label_specific_hotpacks'][k]['weighted_coverage']:.4f}`; "
            f"best bucket coverage: `{best.get('coverage', 0.0):.4f}`."
        )
        lines.append("")
        for idx, group in enumerate(best.get("groups", []), start=1):
            labels_str = ", ".join(group["labels"])
            experts_str = ", ".join(str(expert) for expert in group["hot_expert_ids"][:24])
            lines.append(
                f"- Bucket {idx}: labels `{labels_str}`, coverage `{group['coverage']:.4f}`, "
                f"experts `{experts_str}`"
            )
        lines.append("")
    md = "\n".join(lines) + "\n"
    if args.out_md:
        args.out_md.parent.mkdir(parents=True, exist_ok=True)
        args.out_md.write_text(md)
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
