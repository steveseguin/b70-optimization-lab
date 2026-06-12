#!/usr/bin/env python3
"""CPU-only hotset split break-even model for Qwen3.6 MoE replay windows.

This consumes dry-run JSON emitted by
`bench-qwen36-route-exact-w8a8-grouped-gemm.py --dry-run --hotset-experts ...`.
It does not allocate GPU memory or claim endpoint throughput. The purpose is to
decide whether a hot/cold split is worth a real XPU benchmark, and whether that
benchmark should be a simple two-launch split or a persistent/fused kernel.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any


def parse_float_list(value: str) -> list[float]:
    out = []
    for item in value.split(","):
        item = item.strip()
        if item:
            out.append(float(item))
    if not out:
        raise argparse.ArgumentTypeError("expected at least one float")
    return out


def mean(values: list[float]) -> float:
    return sum(values) / max(1, len(values))


def quantile(values: list[float], q: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def summarize(values: list[float]) -> dict[str, Any]:
    return {
        "min": min(values) if values else math.nan,
        "p50": statistics.median(values) if values else math.nan,
        "mean": mean(values),
        "p95": quantile(values, 0.95),
        "max": max(values) if values else math.nan,
    }


def pct(value: float) -> str:
    if math.isnan(value):
        return "nan"
    return f"{value * 100.0:.1f}%"


def fmt(value: float, digits: int = 1) -> str:
    if math.isnan(value):
        return "nan"
    return f"{value:.{digits}f}"


def source_label(path: Path, payload: dict[str, Any]) -> str:
    stem = path.stem
    route = str(payload.get("route_metadata", {}).get("route_jsonl") or "")
    layers = payload.get("route_metadata", {}).get("layers") or {}
    layer = next(iter(layers.keys()), "")
    if "pcmath" in stem or "math" in stem:
        source = "promptclass-math"
    elif "pcrepetitive" in stem or "repetitive" in stem:
        source = "promptclass-repetitive"
    elif "promptclass" in route:
        source = route.split("promptclass-", 1)[-1].split("-2026", 1)[0]
    elif "routecapture6" in route:
        source = "routecapture6"
    elif "routecapture5" in route:
        source = "routecapture5"
    else:
        source = stem
    if ".layers.9." in layer:
        return f"l9-{source}"
    if ".layers.20." in layer:
        return f"l20-{source}"
    return source


def load_cases(
    paths: list[Path],
    *,
    gemm_stages: int,
) -> list[dict[str, Any]]:
    cases = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        full_num_experts = int(payload.get("full_num_experts") or 0)
        if full_num_experts <= 0:
            raise ValueError(f"{path} is missing full_num_experts")
        label = source_label(path, payload)
        for window in payload.get("selected_windows", []):
            base_active = int(window.get("active_experts") or 0)
            total_rows = int(window.get("total_rows") or 0)
            hotset_split = window.get("hotset_split") or {}
            if not hotset_split:
                continue
            for mode, split in hotset_split.items():
                hot_rows = int(split.get("hot_rows") or 0)
                cold_rows = int(split.get("cold_rows") or 0)
                hot_active = int(split.get("hot_active_experts") or 0)
                cold_active = int(split.get("cold_active_experts") or 0)
                hotset_size = int(split.get("hotset_size") or 0)
                cold_num_experts = int(split.get("cold_num_experts") or 0)
                split_parts = int(hot_rows > 0) + int(cold_rows > 0)
                full_launches = gemm_stages
                split_launches = gemm_stages * split_parts
                split_table_slots = (
                    (hotset_size if hot_rows > 0 else 0) +
                    (cold_num_experts if cold_rows > 0 else 0)
                )
                split_active_slots = hot_active + cold_active
                case = {
                    "input_json": str(path),
                    "source": label,
                    "mode": mode,
                    "case_index": int(window.get("case_index") or 0),
                    "route_start_index": int(window.get("route_start_index") or 0),
                    "route_window_size": int(window.get("route_window_size") or 0),
                    "full_num_experts": full_num_experts,
                    "total_rows": total_rows,
                    "full_active_experts": base_active,
                    "hot_rows": hot_rows,
                    "cold_rows": cold_rows,
                    "hot_coverage": float(split.get("hot_coverage") or 0.0),
                    "hot_active_experts": hot_active,
                    "cold_active_experts": cold_active,
                    "hotset_size": hotset_size,
                    "cold_num_experts": cold_num_experts,
                    "split_table_slots": split_table_slots,
                    "split_active_slots": split_active_slots,
                    "table_slot_ratio": (
                        split_table_slots / full_num_experts
                        if full_num_experts else math.nan
                    ),
                    "active_slot_ratio": (
                        split_active_slots / base_active
                        if base_active else math.nan
                    ),
                    "row_ratio": 1.0,
                    "full_launches": full_launches,
                    "split_launches": split_launches,
                    "extra_launches": max(0, split_launches - full_launches),
                    "cold_present": cold_rows > 0,
                }
                cases.append(case)
    if not cases:
        raise ValueError("No hotset split cases found")
    return cases


def break_even_grid(
    cases: list[dict[str, Any]],
    *,
    baseline_us: list[float],
    launch_overhead_us: list[float],
) -> list[dict[str, Any]]:
    rows = []
    for baseline in baseline_us:
        for launch in launch_overhead_us:
            fractions = []
            speedups = []
            impossible = 0
            for case in cases:
                penalty = float(case["extra_launches"]) * launch
                fraction = (baseline - penalty) / baseline
                if fraction <= 0:
                    impossible += 1
                    fractions.append(0.0)
                    speedups.append(math.inf)
                else:
                    fractions.append(fraction)
                    speedups.append(1.0 / fraction)
            finite_speedups = [item for item in speedups if math.isfinite(item)]
            rows.append({
                "baseline_us": baseline,
                "launch_overhead_us": launch,
                "cases": len(cases),
                "impossible_cases": impossible,
                "max_allowed_body_fraction_mean": mean(fractions),
                "max_allowed_body_fraction_min": min(fractions),
                "required_body_speedup_mean": (
                    mean(finite_speedups) if finite_speedups else math.inf
                ),
                "required_body_speedup_max": (
                    max(finite_speedups) if finite_speedups else math.inf
                ),
            })
    return rows


def group_key(case: dict[str, Any]) -> tuple[str, str]:
    return str(case["source"]), str(case["mode"])


def aggregate_cases(
    cases: list[dict[str, Any]],
    *,
    baseline_us: list[float],
    launch_overhead_us: list[float],
) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for case in cases:
        buckets.setdefault(group_key(case), []).append(case)

    out = []
    for (source, mode), items in sorted(buckets.items()):
        hot_cov = [float(item["hot_coverage"]) for item in items]
        cold_rows = [float(item["cold_rows"]) for item in items]
        cold_active = [float(item["cold_active_experts"]) for item in items]
        table_ratio = [float(item["table_slot_ratio"]) for item in items]
        active_ratio = [float(item["active_slot_ratio"]) for item in items]
        extra_launches = [float(item["extra_launches"]) for item in items]
        out.append({
            "source": source,
            "mode": mode,
            "cases": len(items),
            "hot_coverage": summarize(hot_cov),
            "cold_rows": summarize(cold_rows),
            "cold_active_experts": summarize(cold_active),
            "table_slot_ratio": summarize(table_ratio),
            "active_slot_ratio": summarize(active_ratio),
            "extra_launches": summarize(extra_launches),
            "all_cases_have_cold_fallback": all(item["cold_present"] for item in items),
            "break_even": break_even_grid(
                items,
                baseline_us=baseline_us,
                launch_overhead_us=launch_overhead_us,
            ),
        })
    return out


def make_recommendations(aggregates: list[dict[str, Any]]) -> list[str]:
    recommendations = []
    for item in aggregates:
        source = item["source"]
        mode = item["mode"]
        hot_min = float(item["hot_coverage"]["min"])
        table_mean = float(item["table_slot_ratio"]["mean"])
        extra_mean = float(item["extra_launches"]["mean"])
        if mode == "full":
            if table_mean >= 1.0 and extra_mean > 0:
                recommendations.append(
                    f"{source} full-cold split is a poor two-launch target: "
                    f"mean table slots are {table_mean:.2f}x baseline and "
                    f"every cold fallback adds launches."
                )
        elif mode == "compact":
            if hot_min < 0.70:
                recommendations.append(
                    f"{source} compact-cold split needs stress validation: "
                    f"minimum hot coverage is only {pct(hot_min)}."
                )
            if table_mean < 0.40 and extra_mean > 0:
                recommendations.append(
                    f"{source} compact-cold split has enough table-slot shrink "
                    f"({table_mean:.2f}x baseline) to justify a maintenance-window "
                    f"microbench, but persistent/fused fallback remains the safer "
                    f"production target."
                )
    return recommendations


def make_markdown(report: dict[str, Any], *, primary_baseline: float, primary_launch: float) -> str:
    lines = [
        "# Qwen3.6 Hotset Split Floor Model",
        "",
        "This is a CPU-only model from dry-run route windows. It does not claim",
        "endpoint speed. It estimates whether a hot/cold split can survive the",
        "extra launch penalty before a real XPU benchmark.",
        "",
        f"GEMM stages modeled per MoE layer window: `{report['gemm_stages']}`",
        f"Primary scenario: baseline `{primary_baseline:.1f} us`, launch overhead `{primary_launch:.1f} us`",
        "",
        "## Aggregate Windows",
        "",
        "| source | mode | cases | hot cov min/mean | cold rows max | cold active max | table slots mean/max | extra launches mean | required body speedup |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for item in report["aggregates"]:
        chosen = None
        for row in item["break_even"]:
            if (
                abs(float(row["baseline_us"]) - primary_baseline) < 1e-9 and
                abs(float(row["launch_overhead_us"]) - primary_launch) < 1e-9
            ):
                chosen = row
                break
        speedup = (
            "impossible"
            if chosen is None or math.isinf(float(chosen["required_body_speedup_max"]))
            else f"{float(chosen['required_body_speedup_max']):.2f}x"
        )
        lines.append(
            "| "
            f"{item['source']} | {item['mode']} | {item['cases']} | "
            f"{pct(float(item['hot_coverage']['min']))} / {pct(float(item['hot_coverage']['mean']))} | "
            f"{fmt(float(item['cold_rows']['max']), 0)} | "
            f"{fmt(float(item['cold_active_experts']['max']), 0)} | "
            f"{float(item['table_slot_ratio']['mean']):.2f}x / {float(item['table_slot_ratio']['max']):.2f}x | "
            f"{float(item['extra_launches']['mean']):.1f} | "
            f"{speedup} |"
        )

    lines.extend([
        "",
        "## Interpretation",
        "",
    ])
    for rec in report["recommendations"]:
        lines.append(f"- {rec}")
    if not report["recommendations"]:
        lines.append("- No automatic recommendations generated.")

    lines.extend([
        "",
        "## Break-Even Rule",
        "",
        "- Full path body fraction is normalized to `1.0` for the selected MoE layer window.",
        "- Split path must run at or below `1 - extra_launches * launch_overhead / baseline`.",
        "- If that fraction is negative, a two-launch split cannot break even under that scenario.",
        "- Because row math is unchanged, real wins must come from lower expert/table overhead, better packing, fewer memory round trips, or persistent/fused execution.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run-json",
        action="append",
        required=True,
        help="Dry-run JSON path. Repeat for multiple route sources.",
    )
    parser.add_argument(
        "--gemm-stages",
        type=int,
        default=2,
        help="Grouped-GEMM stages per MoE layer window; Qwen A3B has gate/up and down.",
    )
    parser.add_argument(
        "--baseline-us",
        type=parse_float_list,
        default=parse_float_list("150,200,270"),
        help="Scenario full-path us values for the selected MoE window.",
    )
    parser.add_argument(
        "--launch-overhead-us",
        type=parse_float_list,
        default=parse_float_list("5,10,20,40"),
        help="Scenario launch-overhead us values.",
    )
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--markdown-out")
    parser.add_argument("--primary-baseline-us", type=float, default=200.0)
    parser.add_argument("--primary-launch-overhead-us", type=float, default=10.0)
    args = parser.parse_args()

    paths = [Path(item) for item in args.dry_run_json]
    cases = load_cases(paths, gemm_stages=args.gemm_stages)
    aggregates = aggregate_cases(
        cases,
        baseline_us=args.baseline_us,
        launch_overhead_us=args.launch_overhead_us,
    )
    report = {
        "inputs": [str(path) for path in paths],
        "gemm_stages": args.gemm_stages,
        "baseline_us_scenarios": args.baseline_us,
        "launch_overhead_us_scenarios": args.launch_overhead_us,
        "case_count": len(cases),
        "aggregates": aggregates,
        "recommendations": make_recommendations(aggregates),
        "cases": cases,
    }

    out = Path(args.output_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.markdown_out:
        md = Path(args.markdown_out)
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text(
            make_markdown(
                report,
                primary_baseline=args.primary_baseline_us,
                primary_launch=args.primary_launch_overhead_us,
            ) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
