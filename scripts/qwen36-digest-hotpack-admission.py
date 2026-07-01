#!/usr/bin/env python3
"""Measure hot-pack admission quality from replay-digest rows.

Coverage answers "how many routed rows land in a hot pack." Admission answers
"how often a token/layer can use a hot-only fast lane, and how much cold tail
remains when it cannot." This is the more relevant signal for one-dispatch or
persistent hot/cold MoE layerlets.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


MAGIC = 0x51573336444947


def expand_inputs(patterns: list[str]) -> list[str]:
    paths: list[str] = []
    for pattern in patterns:
        matches = sorted(glob.glob(pattern))
        if matches:
            paths.extend(matches)
        else:
            paths.append(pattern)
    return paths


def parse_int_list(value: str) -> list[int]:
    out: list[int] = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" in item:
            parts = item.split(":")
            if len(parts) not in (2, 3):
                raise argparse.ArgumentTypeError(
                    f"bad range {item!r}; expected start:stop[:step]"
                )
            start = int(parts[0])
            stop = int(parts[1])
            step = int(parts[2]) if len(parts) == 3 else 1
            if step == 0:
                raise argparse.ArgumentTypeError("range step cannot be zero")
            out.extend(range(start, stop, step))
        else:
            out.append(int(item))
    if not out:
        raise argparse.ArgumentTypeError("expected at least one integer")
    return out


def row_fields(values: list[int]) -> dict[str, int]:
    return {
        "magic": values[0],
        "sequence": values[1],
        "layer_index": values[2],
        "num_rows": values[3],
        "topk": values[4],
        "num_experts": values[5],
        "hidden_size": values[6],
        "rows_sum": values[7],
        "rows_nonzero": values[8],
        "rows_max": values[9],
        "route_hash": values[10],
        "row_hash": values[11],
        "output_numel": values[12],
        "output_bytes": values[13],
        "output_hash": values[14],
        "valid_marker": values[15],
    }


def count_vector_from_digest(values: list[int], num_experts: int) -> list[int]:
    counts = [0] * num_experts
    for idx in range(16, len(values) - 1, 2):
        expert = int(values[idx])
        count = int(values[idx + 1])
        if expert >= 0 and count > 0:
            counts[expert] += count
    return counts


def percentile(values: list[float], q: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    idx = (len(ordered) - 1) * q
    lower = math.floor(idx)
    upper = math.ceil(idx)
    if lower == upper:
        return ordered[int(idx)]
    frac = idx - lower
    return ordered[lower] * (1.0 - frac) + ordered[upper] * frac


def load_hotsets(plan_path: str, hot_sizes: list[int]) -> dict[int, dict[int, set[int]]]:
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    layers = plan.get("layers")
    if not isinstance(layers, list):
        raise ValueError(f"{plan_path} does not contain a list-valued layers key")
    hotsets: dict[int, dict[int, set[int]]] = {}
    for layer_info in layers:
        layer = int(layer_info["layer"])
        plans = layer_info.get("plans") or {}
        hotsets[layer] = {}
        for size in hot_sizes:
            entry = plans.get(str(size))
            if not entry:
                raise ValueError(f"Missing hot size {size} for layer {layer}")
            experts = [int(item) for item in entry.get("experts", [])]
            hotsets[layer][size] = set(experts)
    return hotsets


def summarize_bucket(stats: dict[str, Any]) -> dict[str, Any]:
    coverages = stats["coverages"]
    cold_counts = stats["cold_counts"]
    routed_rows = int(stats["routed_rows"])
    hot_rows = int(stats["hot_rows"])
    row_count = int(stats["row_count"])
    cold_hist = Counter(cold_counts)
    return {
        "row_count": row_count,
        "routed_rows": routed_rows,
        "hot_rows": hot_rows,
        "mean_coverage": hot_rows / routed_rows if routed_rows else 0.0,
        "mean_row_coverage": sum(coverages) / len(coverages) if coverages else 0.0,
        "median_row_coverage": statistics.median(coverages) if coverages else math.nan,
        "p10_row_coverage": percentile(coverages, 0.10),
        "p90_row_coverage": percentile(coverages, 0.90),
        "min_row_coverage": min(coverages) if coverages else math.nan,
        "max_row_coverage": max(coverages) if coverages else math.nan,
        "fully_hot_rows": int(stats["fully_hot_rows"]),
        "fully_hot_fraction": (
            stats["fully_hot_rows"] / row_count if row_count else 0.0
        ),
        "mean_cold_rows": sum(cold_counts) / len(cold_counts) if cold_counts else 0.0,
        "cold_rows_histogram": {
            str(key): int(value) for key, value in sorted(cold_hist.items())
        },
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Qwen3.6 Hot-Pack Admission Summary",
        "",
        f"Created: `{result['created_at']}`",
        "",
        "Inputs:",
        "",
        f"- Plan: `{result['plan']}`",
        f"- Digest rows matched: `{result['rows_matched']}`",
        f"- Digest rows skipped: `{result['rows_skipped']}`",
        f"- Filters: `{json.dumps(result['filters'], sort_keys=True)}`",
        "",
        "## Overall",
        "",
        "| hotset | mean coverage | fully hot | median row | p10 row | mean cold rows |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for size, stats in sorted(result["overall"].items(), key=lambda item: int(item[0])):
        lines.append(
            f"| top{size} | `{stats['mean_coverage']:.4f}` | "
            f"`{stats['fully_hot_fraction']:.4f}` | "
            f"`{stats['median_row_coverage']:.4f}` | "
            f"`{stats['p10_row_coverage']:.4f}` | "
            f"`{stats['mean_cold_rows']:.3f}` |"
        )

    lines.extend([
        "",
        "## Layers",
        "",
        "| layer | hotset | mean coverage | fully hot | median row | p10 row | mean cold rows | cold rows histogram |",
        "|---:|---:|---:|---:|---:|---:|---:|---|",
    ])
    for layer, layer_stats in sorted(result["layers"].items(), key=lambda item: int(item[0])):
        for size, stats in sorted(layer_stats.items(), key=lambda item: int(item[0])):
            hist = ",".join(
                f"{key}:{value}"
                for key, value in stats["cold_rows_histogram"].items()
            )
            lines.append(
                f"| {layer} | top{size} | `{stats['mean_coverage']:.4f}` | "
                f"`{stats['fully_hot_fraction']:.4f}` | "
                f"`{stats['median_row_coverage']:.4f}` | "
                f"`{stats['p10_row_coverage']:.4f}` | "
                f"`{stats['mean_cold_rows']:.3f}` | `{hist}` |"
            )
    lines.append("")
    return "\n".join(lines)


def run(args: argparse.Namespace) -> dict[str, Any]:
    hot_sizes = args.hot_sizes
    hotsets = load_hotsets(args.plan, hot_sizes)
    num_rows_filter = set(args.num_rows) if args.num_rows else None
    layers_filter = set(args.layers) if args.layers else None
    local_rank_filter = set(args.local_ranks) if args.local_ranks else None

    def empty_bucket() -> dict[str, Any]:
        return {
            "row_count": 0,
            "routed_rows": 0,
            "hot_rows": 0,
            "fully_hot_rows": 0,
            "coverages": [],
            "cold_counts": [],
        }

    by_layer: dict[int, dict[int, dict[str, Any]]] = defaultdict(
        lambda: defaultdict(empty_bucket)
    )
    overall: dict[int, dict[str, Any]] = defaultdict(empty_bucket)
    rows_seen = 0
    rows_matched = 0
    rows_skipped = 0
    invalid_rows = 0

    for path in expand_inputs(args.inputs):
        with Path(path).open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                record = json.loads(line)
                local_rank = str(record.get("local_rank", ""))
                if (
                    local_rank_filter is not None
                    and local_rank
                    and int(local_rank) not in local_rank_filter
                ):
                    skipped = len(record.get("rows", []))
                    rows_seen += skipped
                    rows_skipped += skipped
                    continue
                for row in record.get("rows", []):
                    rows_seen += 1
                    values = row.get("values")
                    if not isinstance(values, list) or len(values) < 16:
                        invalid_rows += 1
                        rows_skipped += 1
                        continue
                    try:
                        values_i = [int(value) for value in values]
                        fields = row_fields(values_i)
                    except Exception:
                        invalid_rows += 1
                        rows_skipped += 1
                        continue
                    layer = int(fields["layer_index"])
                    if (
                        fields["magic"] != MAGIC
                        or fields["valid_marker"] != 1
                        or layer < 0
                        or layer not in hotsets
                    ):
                        rows_skipped += 1
                        continue
                    if num_rows_filter is not None and fields["num_rows"] not in num_rows_filter:
                        rows_skipped += 1
                        continue
                    if layers_filter is not None and layer not in layers_filter:
                        rows_skipped += 1
                        continue
                    counts = count_vector_from_digest(values_i, fields["num_experts"])
                    routed = sum(counts)
                    if routed <= 0:
                        rows_skipped += 1
                        continue
                    rows_matched += 1
                    for size in hot_sizes:
                        hot = sum(counts[expert] for expert in hotsets[layer][size])
                        cold = routed - hot
                        coverage = hot / routed
                        for bucket in (by_layer[layer][size], overall[size]):
                            bucket["row_count"] += 1
                            bucket["routed_rows"] += routed
                            bucket["hot_rows"] += hot
                            bucket["fully_hot_rows"] += 1 if cold == 0 else 0
                            bucket["coverages"].append(coverage)
                            bucket["cold_counts"].append(cold)

    return {
        "created_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S%z"),
        "purpose": "Measure hot-pack admission and cold-tail shape from replay digest rows.",
        "inputs": expand_inputs(args.inputs),
        "plan": args.plan,
        "filters": {
            "hot_sizes": hot_sizes,
            "num_rows": args.num_rows,
            "layers": args.layers,
            "local_ranks": args.local_ranks,
        },
        "rows_seen": rows_seen,
        "rows_matched": rows_matched,
        "rows_skipped": rows_skipped,
        "invalid_rows": invalid_rows,
        "overall": {
            str(size): summarize_bucket(bucket)
            for size, bucket in sorted(overall.items())
        },
        "layers": {
            str(layer): {
                str(size): summarize_bucket(bucket)
                for size, bucket in sorted(layer_buckets.items())
            }
            for layer, layer_buckets in sorted(by_layer.items())
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", help="Replay-digest JSONL path/glob")
    parser.add_argument("--plan", required=True, help="Hot-pack plan JSON")
    parser.add_argument("--hot-sizes", type=parse_int_list, default=[64, 128])
    parser.add_argument("--num-rows", type=parse_int_list, default=[1])
    parser.add_argument("--layers", type=parse_int_list)
    parser.add_argument("--local-ranks", type=parse_int_list)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run(args)
    Path(args.out_json).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.out_md:
        Path(args.out_md).write_text(render_markdown(result), encoding="utf-8")
    print(json.dumps({
        "rows_matched": result["rows_matched"],
        "overall": result["overall"],
        "out_json": args.out_json,
        "out_md": args.out_md,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
