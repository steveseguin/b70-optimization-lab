#!/usr/bin/env python3
"""Summarize Qwen3.6 MoE route-scan component deltas.

The route replay microbench emits raw and hot-packed JSON files with per-window
component timings. This script pairs those files by layer, row count, and route
start index so route-policy decisions are based on stage-level evidence instead
of only whole-kernel totals.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


TIMING_KEYS = (
    "total_us_mean",
    "preallocated_staged_total_us_mean",
)

COMPONENT_ORDER = (
    "rows_zero",
    "remap",
    "quant1",
    "gemm1",
    "activation",
    "act_contiguous",
    "quant2",
    "activation_plus_quant2",
    "activation_contiguous_quant2",
    "gemm2",
    "gather",
    "component_sum",
)


@dataclass(frozen=True)
class PairSpec:
    label: str
    raw_path: Path
    hot_path: Path


def mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def pct_delta(raw: float | None, hot: float | None) -> float | None:
    if raw is None or hot is None or raw == 0:
        return None
    return (hot - raw) / raw * 100.0


def us_delta(raw: float | None, hot: float | None) -> float | None:
    if raw is None or hot is None:
        return None
    return hot - raw


def parse_pair(value: str) -> PairSpec:
    parts = value.split(":", 2)
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(
            "--pair must be LABEL:RAW_JSON:HOT_JSON")
    label, raw_path, hot_path = parts
    if not label:
        raise argparse.ArgumentTypeError("pair label cannot be empty")
    raw = Path(raw_path)
    hot = Path(hot_path)
    if not raw.exists():
        raise argparse.ArgumentTypeError(f"raw JSON does not exist: {raw}")
    if not hot.exists():
        raise argparse.ArgumentTypeError(f"hot JSON does not exist: {hot}")
    return PairSpec(label=label, raw_path=raw, hot_path=hot)


def load_results(path: Path) -> dict[tuple[int, int], dict[str, Any]]:
    data = json.loads(path.read_text())
    results = data.get("results")
    if not isinstance(results, list):
        raise ValueError(f"{path} is missing list field 'results'")

    indexed: dict[tuple[int, int], dict[str, Any]] = {}
    for result in results:
        if not isinstance(result, dict):
            continue
        rows = result.get("rows")
        start = result.get("route_start_index")
        if rows is None or start is None:
            continue
        key = (int(rows), int(start))
        if key in indexed:
            raise ValueError(f"{path} has duplicate result key {key}")
        indexed[key] = result
    if not indexed:
        raise ValueError(f"{path} has no keyed route results")
    return indexed


def active_experts(result: dict[str, Any]) -> int | None:
    summary = result.get("topk_summary")
    if isinstance(summary, dict) and "active_experts" in summary:
        return int(summary["active_experts"])
    return None


def timing_value(result: dict[str, Any], name: str) -> float | None:
    if name in TIMING_KEYS:
        value = result.get(name)
    else:
        components = result.get("components_us_mean")
        if not isinstance(components, dict):
            return None
        value = components.get(name)
    if value is None:
        return None
    return float(value)


def summarize_metric(entries: list[dict[str, Any]], name: str) -> dict[str, Any]:
    raw_values = [entry["raw"][name] for entry in entries
                  if entry["raw"].get(name) is not None]
    hot_values = [entry["hot"][name] for entry in entries
                  if entry["hot"].get(name) is not None]
    delta_values = [entry["delta_us"][name] for entry in entries
                    if entry["delta_us"].get(name) is not None]
    pct_values = [entry["delta_pct"][name] for entry in entries
                  if entry["delta_pct"].get(name) is not None]

    return {
        "mean_raw_us": mean(raw_values),
        "mean_hot_us": mean(hot_values),
        "mean_delta_us": mean(delta_values),
        "mean_delta_pct": mean(pct_values),
        "min_delta_pct": min(pct_values) if pct_values else None,
        "max_delta_pct": max(pct_values) if pct_values else None,
        "improved_windows": sum(
            1 for value in delta_values if value < 0),
        "regressed_windows": sum(
            1 for value in delta_values if value > 0),
        "windows": len(delta_values),
    }


def summarize_pair(pair: PairSpec) -> dict[str, Any]:
    raw_results = load_results(pair.raw_path)
    hot_results = load_results(pair.hot_path)
    keys = sorted(set(raw_results) & set(hot_results))
    if not keys:
        raise ValueError(
            f"{pair.label}: raw/hot files have no matching rows/start keys")

    missing_raw = sorted(set(hot_results) - set(raw_results))
    missing_hot = sorted(set(raw_results) - set(hot_results))
    timing_names = list(TIMING_KEYS) + list(COMPONENT_ORDER)

    by_rows: dict[int, list[dict[str, Any]]] = defaultdict(list)
    entries: list[dict[str, Any]] = []
    for rows, start in keys:
        raw = raw_results[(rows, start)]
        hot = hot_results[(rows, start)]
        raw_timings = {name: timing_value(raw, name) for name in timing_names}
        hot_timings = {name: timing_value(hot, name) for name in timing_names}
        delta_us = {
            name: us_delta(raw_timings[name], hot_timings[name])
            for name in timing_names
        }
        delta_pct = {
            name: pct_delta(raw_timings[name], hot_timings[name])
            for name in timing_names
        }
        entry = {
            "rows": rows,
            "route_start_index": start,
            "active_experts_raw": active_experts(raw),
            "active_experts_hot": active_experts(hot),
            "raw": raw_timings,
            "hot": hot_timings,
            "delta_us": delta_us,
            "delta_pct": delta_pct,
        }
        entries.append(entry)
        by_rows[rows].append(entry)

    row_summaries: dict[str, Any] = {}
    for rows, row_entries in sorted(by_rows.items()):
        metrics = {
            name: summarize_metric(row_entries, name)
            for name in timing_names
        }
        component_rank = sorted(
            [
                {
                    "component": name,
                    "mean_delta_us": metrics[name]["mean_delta_us"],
                    "mean_delta_pct": metrics[name]["mean_delta_pct"],
                    "improved_windows": metrics[name]["improved_windows"],
                    "regressed_windows": metrics[name]["regressed_windows"],
                }
                for name in COMPONENT_ORDER
                if metrics[name]["mean_delta_us"] is not None
            ],
            key=lambda item: abs(item["mean_delta_us"]),
            reverse=True,
        )
        row_summaries[str(rows)] = {
            "windows": len(row_entries),
            "mean_active_experts_raw": mean([
                entry["active_experts_raw"] for entry in row_entries
                if entry["active_experts_raw"] is not None
            ]),
            "metrics": metrics,
            "component_abs_delta_rank": component_rank,
        }

    return {
        "label": pair.label,
        "raw_path": str(pair.raw_path),
        "hot_path": str(pair.hot_path),
        "matched_windows": len(entries),
        "missing_raw_keys": missing_raw,
        "missing_hot_keys": missing_hot,
        "by_rows": row_summaries,
        "entries": entries,
    }


def print_table(summary: dict[str, Any]) -> None:
    print("label rows windows total_delta_pct prealloc_delta_pct top_component_delta")
    for pair in summary["pairs"]:
        for rows, row_summary in pair["by_rows"].items():
            metrics = row_summary["metrics"]
            total = metrics["total_us_mean"]["mean_delta_pct"]
            prealloc = metrics["preallocated_staged_total_us_mean"][
                "mean_delta_pct"]
            top_components = [
                item for item in row_summary["component_abs_delta_rank"]
                if item["component"] not in (
                    "activation_plus_quant2",
                    "activation_contiguous_quant2",
                    "component_sum",
                )
            ]
            top = top_components[0] if top_components else None
            top_text = "n/a"
            if top:
                top_text = (
                    f"{top['component']}="
                    f"{top['mean_delta_us']:+.3f}us/"
                    f"{top['mean_delta_pct']:+.2f}%")
            print(
                f"{pair['label']} {rows} {row_summary['windows']} "
                f"{total:+.3f}% {prealloc:+.3f}% {top_text}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pair",
        action="append",
        type=parse_pair,
        required=True,
        help="Layer/file pair as LABEL:RAW_JSON:HOTPACK_JSON.",
    )
    parser.add_argument("--output-json", required=True)
    parser.add_argument(
        "--print-table",
        action="store_true",
        help="Print a compact row-level table to stdout.",
    )
    args = parser.parse_args()

    pairs = [summarize_pair(pair) for pair in args.pair]
    summary = {
        "date": date.today().isoformat(),
        "purpose": (
            "Component-level raw-vs-hotpack summary for Qwen3.6 Quark W8A8 "
            "INT8 MoE route replay scans. Negative deltas mean hotpack is "
            "faster than raw for the paired route window."
        ),
        "pairs": pairs,
    }
    out = Path(args.output_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    if args.print_table:
        print_table(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
