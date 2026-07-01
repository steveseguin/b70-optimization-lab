#!/usr/bin/env python3
"""Summarize Qwen3.6 W8A8 offset route-replay and endpoint gates.

This intentionally separates three questions:

1. Does eager no-server route replay remain numerically exact?
2. Is the offset path faster than the accepted/base integration?
3. Did the endpoint provenance gate pass?

The offset endpoint can fail even when eager replay is exact, so this report is
meant to prevent promoting eager-only parity as sufficient evidence.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else math.nan


def metric_values(data: dict[str, Any], name: str) -> list[float]:
    values = []
    for row in data.get("results", []):
        value = row.get(name)
        if value is not None:
            values.append(float(value))
    return values


def max_diff(data: dict[str, Any], names: list[str]) -> float:
    values = []
    for row in data.get("results", []):
        for name in names:
            value = row.get(name)
            if value is not None:
                values.append(float(value))
    return max(values) if values else math.nan


def summarize_replay(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "rows": len(data.get("results", [])),
        "route_metadata": data.get("route_metadata"),
        "mean_xpu_fused_moe_us": mean(
            metric_values(data, "total_us_mean")),
        "mean_xpu_fused_moe_scratch_us": mean(
            metric_values(data, "xpu_fused_moe_scratch_total_us_mean")),
        "mean_fused_prologue_us": mean(
            metric_values(data, "fused_prologue_staged_total_us_mean")),
        "mean_fused_prologue_offset_us": mean(
            metric_values(data, "fused_prologue_offset_gemm_total_us_mean")),
        "max_abs_diff_all_checked_paths": max_diff(data, [
            "manual_vs_xpu_fused_moe_max_abs_diff",
            "xpu_scratch_vs_xpu_fused_moe_max_abs_diff",
            "preallocated_vs_xpu_fused_moe_max_abs_diff",
            "fused_prologue_vs_xpu_fused_moe_max_abs_diff",
            "fused_prologue_offset_gemm_vs_xpu_fused_moe_max_abs_diff",
        ]),
        "offset_gemm_available": any(
            bool(row.get("offset_gemm_available"))
            for row in data.get("results", [])),
        "active_offset_gemm_available": any(
            bool(row.get("active_offset_gemm_available"))
            for row in data.get("results", [])),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    base = report["base_replay"]
    offset = report["offset_env_replay"]
    endpoint = report["endpoint_gate"]
    lines = [
        "# Qwen3.6 W8A8 Offset Route Gate",
        "",
        f"- Decision: `{report['decision']}`.",
        f"- Eager route replay exact: `{report['eager_exact']}`.",
        f"- Offset speed gate passed: `{report['offset_speed_gate_passed']}`.",
        f"- Endpoint provenance passed: `{endpoint.get('ok')}`.",
        "",
        "## No-Server Route Replay",
        "",
        "| profile | rows | mean xpu_fused_moe us | mean scratch us | "
        "mean fused-prologue us | mean fused-prologue offset us | max diff |",
        "|---|---:|---:|---:|---:|---:|---:|",
        (
            f"| base integration | {base['rows']} | "
            f"{base['mean_xpu_fused_moe_us']:.3f} | "
            f"{base['mean_xpu_fused_moe_scratch_us']:.3f} | "
            f"{base['mean_fused_prologue_us']:.3f} | "
            f"{base['mean_fused_prologue_offset_us']:.3f} | "
            f"{base['max_abs_diff_all_checked_paths']:.6f} |"
        ),
        (
            f"| offset env integration | {offset['rows']} | "
            f"{offset['mean_xpu_fused_moe_us']:.3f} | "
            f"{offset['mean_xpu_fused_moe_scratch_us']:.3f} | "
            f"{offset['mean_fused_prologue_us']:.3f} | "
            f"{offset['mean_fused_prologue_offset_us']:.3f} | "
            f"{offset['max_abs_diff_all_checked_paths']:.6f} |"
        ),
        "",
        "## Endpoint Gate",
        "",
    ]
    for sentinel in endpoint.get("sentinels", []):
        lines.append(
            f"- `{sentinel.get('name')}[{sentinel.get('index')}]`: "
            f"expected `{sentinel.get('expected_token_id')}`, "
            f"actual `{sentinel.get('actual_token_id')}`, "
            f"ok `{sentinel.get('ok')}`."
        )
    if endpoint.get("errors"):
        lines.append("")
        lines.append("Endpoint errors:")
        for error in endpoint["errors"]:
            lines.append(f"- {error}")
    lines.extend([
        "",
        "## Interpretation",
        "",
        "- Eager route replay is useful, but it is not sufficient for promotion: "
        "the endpoint failed provenance while this eager gate stayed exact.",
        "- The offset-env integration is slower than base in no-server replay, "
        "so the offset path is rejected on performance even before endpoint "
        "quality is considered.",
        "- The next correctness gate for similar ideas must exercise the "
        "compiled/graph serving path or capture live graph-path tensors, not "
        "only eager synthetic tensors.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-json", type=Path, required=True)
    parser.add_argument("--offset-json", type=Path, required=True)
    parser.add_argument("--endpoint-provenance-json", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--markdown-out", type=Path)
    parser.add_argument("--max-speed-regression-pct", type=float, default=2.0)
    args = parser.parse_args()

    base_data = load_json(args.base_json)
    offset_data = load_json(args.offset_json)
    endpoint_data = load_json(args.endpoint_provenance_json)

    base_summary = summarize_replay(base_data)
    offset_summary = summarize_replay(offset_data)
    speed_ratio = (
        offset_summary["mean_xpu_fused_moe_us"] /
        base_summary["mean_xpu_fused_moe_us"])
    speed_gate = speed_ratio <= (1.0 + args.max_speed_regression_pct / 100.0)
    eager_exact = (
        base_summary["max_abs_diff_all_checked_paths"] == 0.0 and
        offset_summary["max_abs_diff_all_checked_paths"] == 0.0)
    endpoint_ok = bool(endpoint_data.get("ok"))
    decision = (
        "rejected"
        if (not eager_exact or not speed_gate or not endpoint_ok)
        else "candidate"
    )

    report = {
        "kind": "qwen36_w8a8_offset_route_gate_summary",
        "base_json": str(args.base_json),
        "offset_json": str(args.offset_json),
        "endpoint_provenance_json": str(args.endpoint_provenance_json),
        "base_replay": base_summary,
        "offset_env_replay": offset_summary,
        "offset_vs_base_xpu_fused_moe_us_ratio": speed_ratio,
        "offset_vs_base_xpu_fused_moe_us_delta_pct":
        (speed_ratio - 1.0) * 100.0,
        "max_speed_regression_pct": args.max_speed_regression_pct,
        "eager_exact": eager_exact,
        "offset_speed_gate_passed": speed_gate,
        "endpoint_gate": {
            "ok": endpoint_ok,
            "sentinels": endpoint_data.get("sentinels", []),
            "errors": endpoint_data.get("errors", []),
        },
        "decision": decision,
        "next_gate": (
            "compiled/graph-path tensor parity or live graph-path tensor "
            "capture before any endpoint promotion"
        ),
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        write_markdown(args.markdown_out, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
