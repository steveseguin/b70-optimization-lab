#!/usr/bin/env python3
"""Overlay replay-digest route signatures with all-rank forward timing."""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


MAGIC = 0x51573336444947


def expand_inputs(patterns: list[str]) -> list[str]:
    paths: list[str] = []
    for pattern in patterns:
        matches = sorted(glob.glob(pattern))
        paths.extend(matches or [pattern])
    out = []
    seen = set()
    for path in paths:
        if path not in seen:
            seen.add(path)
            out.append(path)
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


def hot_expert_pairs(values: list[int]) -> list[tuple[int, int]]:
    pairs = []
    for idx in range(16, len(values) - 1, 2):
        expert = int(values[idx])
        count = int(values[idx + 1])
        if expert >= 0 and count > 0:
            pairs.append((expert, count))
    return pairs


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:16]


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def stddev(values: list[float]) -> float | None:
    if len(values) < 2:
        return 0.0 if values else None
    m = sum(values) / len(values)
    return math.sqrt(sum((value - m) ** 2 for value in values) / len(values))


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    den = math.sqrt(sum(x * x for x in dx) * sum(y * y for y in dy))
    if den == 0:
        return None
    return sum(x * y for x, y in zip(dx, dy)) / den


def counter_fingerprint(counter: Counter[Any]) -> str:
    return stable_hash(sorted((str(key), int(value)) for key, value in counter.items()))


def top_coverage(counter: Counter[Any], k: int, denom: int) -> float:
    if not denom:
        return 0.0
    return sum(count for _key, count in counter.most_common(k)) / denom


def parse_forward_rank_means(path: Path) -> dict[str, float]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("pure_decode_after_first5_each_rank_by_rank") or {}
    out = {}
    for rank, metrics in rows.items():
        mean_value = (
            metrics.get("forward_end_after_start_sync_ms", {}).get("mean")
        )
        if mean_value is not None:
            out[str(rank)] = float(mean_value)
    return out


def parse_rankmap(path: Path | None) -> dict[str, int]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    raw = data.get("rank_to_physical_device_id") or {}
    return {str(key): int(value) for key, value in raw.items()}


def summarize_routes(paths: list[str], num_rows: int) -> dict[str, Any]:
    route_by_rank_layer: dict[tuple[str, int], Counter[int]] = defaultdict(Counter)
    hot_by_rank_layer: dict[tuple[str, int], Counter[int]] = defaultdict(Counter)
    row_counts: Counter[str] = Counter()
    rows_by_rank_layer: Counter[tuple[str, int]] = Counter()
    invalid_rows = 0
    loaded_rows = 0
    filtered_rows = 0
    sources = expand_inputs(paths)

    for source in sources:
        with Path(source).open("r", encoding="utf-8") as handle:
            for lineno, line in enumerate(handle, 1):
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                rank = str(record.get("local_rank") or record.get("rank") or "")
                if rank == "":
                    rank = str(record.get("device") or "unknown")
                for row in record.get("rows", []):
                    loaded_rows += 1
                    values = row.get("values")
                    if not isinstance(values, list) or len(values) < 16:
                        invalid_rows += 1
                        continue
                    try:
                        values_i = [int(value) for value in values]
                        fields = row_fields(values_i)
                    except Exception:
                        invalid_rows += 1
                        continue
                    if fields["magic"] != MAGIC or fields["valid_marker"] != 1:
                        invalid_rows += 1
                        continue
                    if fields["layer_index"] < 0 or fields["num_rows"] != num_rows:
                        filtered_rows += 1
                        continue
                    layer = int(fields["layer_index"])
                    route_by_rank_layer[(rank, layer)][int(fields["route_hash"])] += 1
                    rows_by_rank_layer[(rank, layer)] += 1
                    row_counts[rank] += 1
                    for expert, count in hot_expert_pairs(values_i):
                        hot_by_rank_layer[(rank, layer)][expert] += count

    ranks = sorted(row_counts, key=lambda item: int(item) if item.isdigit() else item)
    layers = sorted({layer for _rank, layer in rows_by_rank_layer})
    by_rank: dict[str, Any] = {}
    route_layer_fingerprints_by_rank: dict[str, dict[int, str]] = {}
    hot_layer_fingerprints_by_rank: dict[str, dict[int, str]] = {}

    for rank in ranks:
        unique_routes = []
        top1 = []
        top4 = []
        top16 = []
        hot_unique = []
        hot_top16 = []
        route_fps: dict[int, str] = {}
        hot_fps: dict[int, str] = {}
        for layer in layers:
            route_counter = route_by_rank_layer[(rank, layer)]
            hot_counter = hot_by_rank_layer[(rank, layer)]
            denom = rows_by_rank_layer[(rank, layer)]
            if denom:
                unique_routes.append(float(len(route_counter)))
                top1.append(top_coverage(route_counter, 1, denom))
                top4.append(top_coverage(route_counter, 4, denom))
                top16.append(top_coverage(route_counter, 16, denom))
                route_fps[layer] = counter_fingerprint(route_counter)
            hot_denom = sum(hot_counter.values())
            if hot_denom:
                hot_unique.append(float(len(hot_counter)))
                hot_top16.append(top_coverage(hot_counter, 16, hot_denom))
                hot_fps[layer] = counter_fingerprint(hot_counter)
        route_layer_fingerprints_by_rank[rank] = route_fps
        hot_layer_fingerprints_by_rank[rank] = hot_fps
        by_rank[rank] = {
            "route_rows": int(row_counts[rank]),
            "layers": len([layer for layer in layers if rows_by_rank_layer[(rank, layer)]]),
            "mean_unique_route_hashes_per_layer": mean(unique_routes),
            "mean_top1_route_hash_coverage": mean(top1),
            "mean_top4_route_hash_coverage": mean(top4),
            "mean_top16_route_hash_coverage": mean(top16),
            "mean_unique_hot_experts_per_layer": mean(hot_unique),
            "mean_top16_hot_expert_coverage": mean(hot_top16),
        }

    def identical_layer_count(fps_by_rank: dict[str, dict[int, str]]) -> int:
        identical = 0
        for layer in layers:
            values = [fps_by_rank.get(rank, {}).get(layer) for rank in ranks]
            if values and all(value is not None for value in values) and all(value == values[0] for value in values):
                identical += 1
        return identical

    hot_layers_with_data = 0
    hot_identical_layers = 0
    for layer in layers:
        values = [hot_layer_fingerprints_by_rank.get(rank, {}).get(layer) for rank in ranks]
        if values and all(value is not None for value in values):
            hot_layers_with_data += 1
            if all(value == values[0] for value in values):
                hot_identical_layers += 1

    return {
        "sources": sources,
        "num_rows_filter": num_rows,
        "loaded_rows": loaded_rows,
        "filtered_rows": filtered_rows,
        "invalid_rows": invalid_rows,
        "ranks": ranks,
        "layers": layers,
        "by_rank": by_rank,
        "route_counter_identical_layers_across_ranks": identical_layer_count(route_layer_fingerprints_by_rank),
        "hot_counter_identical_layers_across_ranks": hot_identical_layers,
        "hot_counter_layers_with_data": hot_layers_with_data,
        "layer_count": len(layers),
    }


def build_overlay(args: argparse.Namespace) -> dict[str, Any]:
    forward = parse_forward_rank_means(Path(args.forward_summary))
    rankmap = parse_rankmap(Path(args.rankmap_summary) if args.rankmap_summary else None)
    routes = summarize_routes(args.route_inputs, args.num_rows)
    by_rank = routes["by_rank"]

    metric_names = [
        "mean_unique_route_hashes_per_layer",
        "mean_top1_route_hash_coverage",
        "mean_top4_route_hash_coverage",
        "mean_top16_route_hash_coverage",
        "mean_unique_hot_experts_per_layer",
        "mean_top16_hot_expert_coverage",
    ]
    correlations = {}
    ranks = [rank for rank in routes["ranks"] if rank in forward]
    for metric in metric_names:
        pairs = [
            (forward[rank], by_rank[rank][metric])
            for rank in ranks
            if by_rank[rank][metric] is not None
        ]
        correlations[metric] = pearson(
            [pair[0] for pair in pairs],
            [pair[1] for pair in pairs],
        )

    route_metric_spreads = {}
    for metric in metric_names:
        values = [by_rank[rank][metric] for rank in routes["ranks"] if by_rank[rank][metric] is not None]
        route_metric_spreads[metric] = {
            "min": min(values) if values else None,
            "max": max(values) if values else None,
            "spread": (max(values) - min(values)) if values else None,
            "stddev": stddev(values),
        }

    for rank, row in by_rank.items():
        row["forward_end_after_start_sync_mean_ms"] = forward.get(rank)
        row["physical_device_after_rankmap_reversal"] = rankmap.get(rank)

    route_identical = routes["route_counter_identical_layers_across_ranks"]
    hot_identical = routes["hot_counter_identical_layers_across_ranks"]
    hot_layers_with_data = routes["hot_counter_layers_with_data"]
    layer_count = routes["layer_count"]
    if route_identical == layer_count and (hot_layers_with_data == 0 or hot_identical == hot_layers_with_data):
        decision = "route_distribution_is_rank_invariant"
    elif route_identical >= layer_count * 0.9:
        decision = "route_distribution_nearly_rank_invariant"
    else:
        decision = "route_distribution_varies_by_rank"

    return {
        "source_forward_summary": args.forward_summary,
        "source_rankmap_summary": args.rankmap_summary,
        "route_inputs": routes["sources"],
        "num_rows_filter": args.num_rows,
        "decision": decision,
        "interpretation": [
            "This is a CPU-side overlay of replay-digest route signatures and all-rank forward timing.",
            "It does not prove kernel causality, but it can reject simple rank route-skew explanations.",
            "If route and hot-expert counters are rank-invariant, the next probe should split forward time by layer family and collectives rather than generate rank-specific route kernels.",
        ],
        "forward_rank_means_ms": forward,
        "rankmap_reversed_rank_to_physical_device": rankmap,
        "route_summary": {
            "loaded_rows": routes["loaded_rows"],
            "filtered_rows": routes["filtered_rows"],
            "invalid_rows": routes["invalid_rows"],
            "layer_count": layer_count,
            "route_counter_identical_layers_across_ranks": route_identical,
            "hot_counter_identical_layers_across_ranks": hot_identical,
            "hot_counter_layers_with_data": hot_layers_with_data,
            "metric_spreads": route_metric_spreads,
            "correlation_with_forward_mean": correlations,
            "by_rank": by_rank,
        },
        "next_step": (
            "Add layer-family timing around attention, router, expert gather, expert GEMM, combine, and collectives on the slow ranks."
        ),
    }


def write_markdown(data: dict[str, Any], path: Path) -> None:
    summary = data["route_summary"]

    def fmt(value: Any, digits: int = 6) -> str:
        if value is None:
            return "n/a"
        if isinstance(value, float):
            return f"{value:.{digits}f}"
        return str(value)

    lines = [
        "# Qwen3.6 Rank Route Forward Overlay 20260613n",
        "",
        "This is a CPU-side diagnostic overlay, not a new speed benchmark.",
        "",
        "## Decision",
        "",
        f"- Decision: `{data['decision']}`.",
        f"- Decode row filter: `num_rows={data['num_rows_filter']}`.",
        f"- Route-counter identical layers across ranks: `{summary['route_counter_identical_layers_across_ranks']}/{summary['layer_count']}`.",
        f"- Hot-expert-counter identical layers across ranks: `{summary['hot_counter_identical_layers_across_ranks']}/{summary['hot_counter_layers_with_data']}` with payload data.",
        f"- Hot-expert payload present: `{'yes' if summary['hot_counter_layers_with_data'] else 'no'}`.",
        f"- Next step: {data['next_step']}",
        "",
        "## Per-Rank Overlay",
        "",
        "| Rank | Forward end wait ms | Route rows | Unique route hashes/layer | Top16 route coverage | Unique hot experts/layer | Top16 hot coverage | Reversed physical card |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for rank, row in sorted(data["route_summary"]["by_rank"].items(), key=lambda item: int(item[0])):
        lines.append(
            f"| {rank} | "
            f"{row['forward_end_after_start_sync_mean_ms']:.6f} | "
            f"{row['route_rows']} | "
            f"{row['mean_unique_route_hashes_per_layer']:.3f} | "
            f"{row['mean_top16_route_hash_coverage']:.6f} | "
            f"{fmt(row['mean_unique_hot_experts_per_layer'], 3)} | "
            f"{fmt(row['mean_top16_hot_expert_coverage'], 6)} | "
            f"{fmt(row.get('physical_device_after_rankmap_reversal'))} |"
        )
    lines.extend([
        "",
        "## Metric Spreads",
        "",
        "| Metric | Min | Max | Spread | Stddev | Pearson vs forward wait |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ])
    correlations = summary["correlation_with_forward_mean"]
    for metric, spread in summary["metric_spreads"].items():
        corr = correlations.get(metric)
        corr_s = "null" if corr is None else f"{corr:.6f}"
        lines.append(
            f"| `{metric}` | {fmt(spread['min'])} | {fmt(spread['max'])} | "
            f"{fmt(spread['spread'])} | {fmt(spread['stddev'])} | {corr_s} |"
        )
    lines.extend([
        "",
        "## Interpretation",
        "",
    ])
    for item in data["interpretation"]:
        lines.append(f"- {item}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--forward-summary", required=True)
    parser.add_argument("--rankmap-summary")
    parser.add_argument("--num-rows", type=int, default=1)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--md-out", required=True)
    parser.add_argument("route_inputs", nargs="+")
    args = parser.parse_args()

    data = build_overlay(args)
    Path(args.json_out).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(data, Path(args.md_out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
