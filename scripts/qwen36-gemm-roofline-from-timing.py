#!/usr/bin/env python3
"""Summarize Qwen3.6 W8A8 grouped-GEMM timing as a roofline packet.

The input is produced by `bench-qwen36-hotrep-route-plan-gemm.py`. This script
does not need a GPU. It estimates per-stage math work, active-weight memory
traffic, full-table memory traffic, effective TOPS, and implied bandwidth from
already-captured route-exact timings.

This is intentionally conservative: it cannot prove DPAS/XMX instruction use
without hardware counters, but it can show whether the measured grouped-GEMM
shape is anywhere near a compute-saturation regime.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any


def mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else math.nan


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * pct
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return ordered[lo]
    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def summarize(values: list[float]) -> dict[str, float]:
    return {
        "count": len(values),
        "mean": mean(values),
        "median": statistics.median(values) if values else math.nan,
        "p05": percentile(values, 0.05),
        "p95": percentile(values, 0.95),
        "min": min(values) if values else math.nan,
        "max": max(values) if values else math.nan,
    }


def stage_math_and_bytes(
    *,
    rows: int,
    active_experts: int,
    experts: int,
    k: int,
    n: int,
    output_bytes: int,
) -> dict[str, float]:
    # Count multiply and add separately, matching common TOPS reporting.
    ops = 2.0 * rows * k * n
    a_bytes = rows * k
    a_scale_bytes = rows * 4
    active_b_bytes = active_experts * k * n
    full_b_bytes = experts * k * n
    active_b_scale_bytes = active_experts * n * 4
    full_b_scale_bytes = experts * n * 4
    d_bytes = rows * n * output_bytes
    rows_per_expert_bytes = experts * 4

    active_bytes = (
        a_bytes + a_scale_bytes + active_b_bytes + active_b_scale_bytes +
        d_bytes + rows_per_expert_bytes
    )
    full_table_bytes = (
        a_bytes + a_scale_bytes + full_b_bytes + full_b_scale_bytes + d_bytes +
        rows_per_expert_bytes
    )
    return {
        "ops": ops,
        "a_bytes": float(a_bytes + a_scale_bytes),
        "active_weight_bytes": float(active_b_bytes + active_b_scale_bytes),
        "full_table_weight_bytes": float(full_b_bytes + full_b_scale_bytes),
        "output_bytes": float(d_bytes),
        "rows_per_expert_bytes": float(rows_per_expert_bytes),
        "active_lower_bound_bytes": float(active_bytes),
        "full_table_upper_bound_bytes": float(full_table_bytes),
        "arithmetic_intensity_active_ops_per_byte": (
            ops / active_bytes if active_bytes else math.nan
        ),
        "arithmetic_intensity_full_table_ops_per_byte": (
            ops / full_table_bytes if full_table_bytes else math.nan
        ),
    }


def metric_row(
    *,
    mode: str,
    stage: str,
    plan_index: int,
    route_start_index: int,
    rows: int,
    experts: int,
    active_experts: int,
    k: int,
    n: int,
    mean_us: float,
    output_bytes: int,
    rank: int | None = None,
    component: str | None = None,
) -> dict[str, Any]:
    calc = stage_math_and_bytes(
        rows=rows,
        active_experts=active_experts,
        experts=experts,
        k=k,
        n=n,
        output_bytes=output_bytes,
    )
    seconds = mean_us * 1e-6
    ops = calc["ops"]
    active_bytes = calc["active_lower_bound_bytes"]
    full_bytes = calc["full_table_upper_bound_bytes"]
    out = {
        "mode": mode,
        "stage": stage,
        "plan_index": plan_index,
        "route_start_index": route_start_index,
        "rank": rank,
        "component": component,
        "rows": rows,
        "experts": experts,
        "active_experts": active_experts,
        "k": k,
        "n": n,
        "mean_us": mean_us,
        **calc,
        "effective_tops": (ops / seconds / 1e12) if seconds > 0 else math.nan,
        "active_lower_bound_bandwidth_tb_s": (
            active_bytes / seconds / 1e12 if seconds > 0 else math.nan
        ),
        "full_table_upper_bound_bandwidth_tb_s": (
            full_bytes / seconds / 1e12 if seconds > 0 else math.nan
        ),
    }
    return out


def exact_rows(stage_results: list[dict[str, Any]], output_bytes: int) -> list[dict[str, Any]]:
    rows = []
    for item in stage_results:
        if item.get("mode") != "exact_full":
            continue
        rows.append(
            metric_row(
                mode=str(item["mode"]),
                stage=str(item["stage"]),
                plan_index=int(item["plan_index"]),
                route_start_index=int(item["route_start_index"]),
                rows=int(item["rows"]),
                experts=int(item["experts"]),
                active_experts=int(item["active_experts"]),
                k=int(item["k"]),
                n=int(item["n"]),
                mean_us=float(item["mean_us"]),
                output_bytes=output_bytes,
            )
        )
    return rows


def hotrep_rankmax_rows(stage_results: list[dict[str, Any]], output_bytes: int) -> list[dict[str, Any]]:
    rows = []
    for item in stage_results:
        mode = str(item.get("mode") or "")
        if not mode.startswith("hotrep_"):
            continue
        stage = str(item["stage"])
        plan_index = int(item["plan_index"])
        route_start_index = int(item["route_start_index"])
        if mode == "hotrep_one_launch_rankmax":
            rank_results = item.get("rank_results") or []
            if not rank_results:
                continue
            chosen = max(rank_results, key=lambda row: float(row.get("mean_us") or 0.0))
            rows.append(
                metric_row(
                    mode=mode,
                    stage=stage,
                    plan_index=plan_index,
                    route_start_index=route_start_index,
                    rows=int(chosen["rows"]),
                    experts=int(chosen["experts"]),
                    active_experts=int(chosen["active_experts"]),
                    k=int(chosen["k"]),
                    n=int(chosen["n"]),
                    mean_us=float(chosen["mean_us"]),
                    output_bytes=output_bytes,
                    rank=int(chosen["rank"]),
                    component="rankmax_combined",
                )
            )
        elif mode == "hotrep_two_launch_rankmax":
            rank_results = item.get("rank_results") or []
            if not rank_results:
                continue
            chosen = max(rank_results, key=lambda row: float(row.get("rank_sum_mean_us") or 0.0))
            for component in ("hot", "cold"):
                sub = chosen.get(component) or {}
                mean_us = float(sub.get("mean_us") or 0.0)
                if mean_us <= 0.0 or int(sub.get("rows") or 0) <= 0:
                    continue
                rows.append(
                    metric_row(
                        mode=mode,
                        stage=stage,
                        plan_index=plan_index,
                        route_start_index=route_start_index,
                        rows=int(sub["rows"]),
                        experts=int(sub["experts"]),
                        active_experts=int(sub["active_experts"]),
                        k=int(sub["k"]),
                        n=int(sub["n"]),
                        mean_us=mean_us,
                        output_bytes=output_bytes,
                        rank=int(chosen["rank"]),
                        component=component,
                    )
                )
    return rows


def aggregate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (
            str(row["mode"]),
            str(row["stage"]),
            str(row.get("component") or "stage"),
        )
        buckets.setdefault(key, []).append(row)

    out = []
    for (mode, stage, component), items in sorted(buckets.items()):
        out.append({
            "mode": mode,
            "stage": stage,
            "component": component,
            "cases": len(items),
            "rows": summarize([float(item["rows"]) for item in items]),
            "experts": summarize([float(item["experts"]) for item in items]),
            "active_experts": summarize([float(item["active_experts"]) for item in items]),
            "k": summarize([float(item["k"]) for item in items]),
            "n": summarize([float(item["n"]) for item in items]),
            "mean_us": summarize([float(item["mean_us"]) for item in items]),
            "effective_tops": summarize([float(item["effective_tops"]) for item in items]),
            "active_lower_bound_bandwidth_tb_s": summarize([
                float(item["active_lower_bound_bandwidth_tb_s"]) for item in items
            ]),
            "full_table_upper_bound_bandwidth_tb_s": summarize([
                float(item["full_table_upper_bound_bandwidth_tb_s"]) for item in items
            ]),
            "arithmetic_intensity_active_ops_per_byte": summarize([
                float(item["arithmetic_intensity_active_ops_per_byte"]) for item in items
            ]),
            "arithmetic_intensity_full_table_ops_per_byte": summarize([
                float(item["arithmetic_intensity_full_table_ops_per_byte"]) for item in items
            ]),
        })
    return out


def write_markdown(path: str, result: dict[str, Any]) -> None:
    lines = []
    lines.append("# Qwen3.6 W8A8 Grouped-GEMM Roofline Packet")
    lines.append("")
    lines.append(f"Input: `{result['metadata']['timing_json']}`")
    lines.append("")
    lines.append("## Tooling Boundary")
    lines.append("")
    lines.append(
        "- This is an offline estimate from route-exact grouped-GEMM event timings. "
        "It does not include hardware DPAS/XMX counters."
    )
    if result["metadata"].get("counter_limitation"):
        lines.append(f"- Counter limitation: {result['metadata']['counter_limitation']}")
    lines.append(
        "- `active_lower_bound` assumes only active expert weights are read. "
        "`full_table_upper_bound` assumes the full expert table could be touched. "
        "Reality should sit between those bounds."
    )
    lines.append("")
    lines.append("## Aggregate")
    lines.append("")
    lines.append(
        "| mode | stage | component | cases | us mean | TOPS mean | "
        "active BW TB/s | full-table BW TB/s | shape mean | experts mean | active experts mean |"
    )
    lines.append("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in result["aggregate"]:
        lines.append(
            f"| `{row['mode']}` | `{row['stage']}` | `{row['component']}` | "
            f"{row['cases']} | "
            f"{row['mean_us']['mean']:.3f} | "
            f"{row['effective_tops']['mean']:.3f} | "
            f"{row['active_lower_bound_bandwidth_tb_s']['mean']:.3f} | "
            f"{row['full_table_upper_bound_bandwidth_tb_s']['mean']:.3f} | "
            f"{row['rows']['mean']:.1f}x{row['k']['mean']:.0f}x{row['n']['mean']:.0f} | "
            f"{row['experts']['mean']:.1f} | "
            f"{row['active_experts']['mean']:.1f} |"
        )
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    exact = [
        row for row in result["aggregate"]
        if row["mode"] == "exact_full" and row["component"] == "stage"
    ]
    for row in exact:
        lines.append(
            f"- `{row['stage']}` exact_full averages "
            f"`{row['effective_tops']['mean']:.3f}` effective TOPS at "
            f"`{row['mean_us']['mean']:.3f} us` for mean route-window shape "
            f"`M={row['rows']['mean']:.0f}, K={row['k']['mean']:.0f}, "
            f"N={row['n']['mean']:.0f}` with "
            f"`{row['active_experts']['mean']:.1f}` active experts."
        )
    lines.append(
        "- Effective TOPS are very low for a B70-class INT8 path, which is "
        "consistent with small-M/skewed-expert grouped-GEMM underutilization, "
        "launch/control overhead, or a non-ideal kernel path."
    )
    lines.append(
        "- This supports persistent/tile-native MoE work over more service flag "
        "tuning. A speed candidate needs to raise effective TOPS on these exact "
        "route windows or amortize multiple target tokens per forward with an "
        "exact verifier."
    )
    lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timing-json", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--markdown-out")
    parser.add_argument(
        "--output-bytes",
        type=int,
        default=2,
        help="Output element width in bytes. BF16/FP16 grouped-GEMM output uses 2.",
    )
    parser.add_argument(
        "--counter-limitation",
        default=(
            "unitrace/VTune are not installed; xpu-smi EU and bandwidth metrics "
            "require elevated MEI access in this environment."
        ),
    )
    args = parser.parse_args()

    data = json.loads(Path(args.timing_json).read_text(encoding="utf-8"))
    rows = exact_rows(data["stage_results"], args.output_bytes)
    rows.extend(hotrep_rankmax_rows(data["stage_results"], args.output_bytes))
    result = {
        "metadata": {
            "timing_json": args.timing_json,
            "source_metadata": data.get("metadata", {}),
            "output_bytes": args.output_bytes,
            "counter_limitation": args.counter_limitation,
        },
        "rows": rows,
        "aggregate": aggregate_rows(rows),
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
