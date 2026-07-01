#!/usr/bin/env python3
"""Compute the Qwen3.6 MoE fusion target needed for >200 tok/s decode.

This is a CPU-only planning artifact. It combines:

- live endpoint decode timing,
- model-forward-only timing,
- route-exact MoE replay timings with numeric parity,
- and grouped-GEMM small-M floor timings.

The output is not a speed claim. It is the target budget the next
fused/persistent MoE prototype must beat without changing model math.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any


DEFAULT_MODEL_CONFIG = (
    "/mnt/fast-ai/llm-cache/hf/models--nameistoken--"
    "Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/"
    "cced56592e8c8935f8220836b4baa04dfd389118/config.json"
)


def mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else math.nan


def summarize(values: list[float]) -> dict[str, Any]:
    return {
        "count": len(values),
        "mean": mean(values),
        "median": statistics.median(values) if values else math.nan,
        "min": min(values) if values else math.nan,
        "max": max(values) if values else math.nan,
        "stdev": statistics.pstdev(values) if len(values) > 1 else 0.0,
    }


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def nested_mean(data: dict[str, Any], path: list[str]) -> float:
    cur: Any = data
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return math.nan
        cur = cur[key]
    try:
        return float(cur)
    except (TypeError, ValueError):
        return math.nan


def endpoint_decode_ms(path: str) -> dict[str, float]:
    data = load_json(path)
    summary = data.get("summary", {})
    return {
        "decode_ms_per_token": nested_mean(
            summary,
            ["decode_ms_per_generation_token_vllm_histogram", "mean"],
        ),
        "corrected_tok_s": nested_mean(
            summary,
            ["tok_s_out_client_after_first_chunk_corrected", "mean"],
        ),
        "e2e_tok_s": nested_mean(
            summary,
            ["tok_s_out_client_e2e", "mean"],
        ),
    }


def model_forward_ms(path: str) -> float:
    data = load_json(path)
    buckets = data.get("step_summary_by_bucket", [])
    candidates = []
    for row in buckets:
        group = row.get("group", {})
        if group.get("is_pure_decode") is True:
            value = row.get("mean_model_forward_ms")
            if value is not None:
                candidates.append(float(value))
    if candidates:
        return mean(candidates)
    rows = data.get("step_summary_by_mean_total_ms", [])
    values = [
        float(row["mean_total_ms_per_step"])
        for row in rows
        if row.get("label") == "gpu_model_runner.model_forward"
    ]
    return mean(values)


def text_config(path: str) -> dict[str, Any]:
    cfg = load_json(path)
    text = cfg.get("text_config")
    if not isinstance(text, dict):
        raise ValueError(f"missing text_config in {path}")
    return text


def collect_route_replay(paths: list[str], rows_filter: set[int]) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    replay_timing_fields = [
        ("xpu_fused_moe_us", "total_us_mean", True),
        ("preallocated_staged_us", "preallocated_staged_total_us_mean", True),
        ("fused_prologue_staged_us", "fused_prologue_staged_total_us_mean", False),
        ("fused_prologue_offset_gemm_us", "fused_prologue_offset_gemm_total_us_mean", False),
        ("fused_prologue_active_offset_gemm_us", "fused_prologue_active_offset_gemm_total_us_mean", False),
        ("xpu_fused_moe_scratch_us", "xpu_fused_moe_scratch_total_us_mean", False),
    ]
    max_diffs = {
        "manual": [],
        "preallocated": [],
        "fused_prologue": [],
        "fused_prologue_offset_gemm": [],
        "fused_prologue_active_offset_gemm": [],
        "scratch": [],
    }
    component_names = [
        "rows_zero",
        "remap",
        "quant1",
        "gemm1",
        "activation",
        "act_contiguous",
        "quant2",
        "gemm2",
        "gather",
        "activation_plus_quant2",
        "activation_contiguous_quant2",
        "component_sum",
    ]
    components: dict[str, list[float]] = {name: [] for name in component_names}

    for path in paths:
        data = load_json(path)
        for result in data.get("results", []):
            rows = int(result.get("rows", -1))
            if rows_filter and rows not in rows_filter:
                continue
            sample = {
                "source_path": path,
                "rows": rows,
                "route_start_index": result.get("route_start_index"),
                "active_experts": (
                    result.get("topk_summary", {}).get("active_experts")
                    if isinstance(result.get("topk_summary"), dict)
                    else None
                ),
            }
            for sample_key, result_key, required in replay_timing_fields:
                value = result.get(result_key)
                if value is None:
                    if required:
                        raise KeyError(f"{result_key} missing from {path}")
                    sample[sample_key] = None
                else:
                    sample[sample_key] = float(value)
            samples.append(sample)
            for key, diff_key in (
                ("manual", "manual_vs_xpu_fused_moe_max_abs_diff"),
                ("preallocated", "preallocated_vs_xpu_fused_moe_max_abs_diff"),
                ("fused_prologue", "fused_prologue_vs_xpu_fused_moe_max_abs_diff"),
                ("fused_prologue_offset_gemm", "fused_prologue_offset_gemm_vs_xpu_fused_moe_max_abs_diff"),
                ("fused_prologue_active_offset_gemm", "fused_prologue_active_offset_gemm_vs_xpu_fused_moe_max_abs_diff"),
                ("scratch", "xpu_scratch_vs_xpu_fused_moe_max_abs_diff"),
            ):
                value = result.get(diff_key)
                if value is not None:
                    max_diffs[key].append(float(value))
            comp = result.get("components_us_mean", {})
            if isinstance(comp, dict):
                for name in component_names:
                    value = comp.get(name)
                    if value is not None:
                        components[name].append(float(value))

    if not samples:
        raise ValueError("no route replay samples matched filters")

    by_rows: dict[str, Any] = {}
    for rows in sorted({sample["rows"] for sample in samples}):
        row_samples = [sample for sample in samples if sample["rows"] == rows]
        row_summary: dict[str, Any] = {
            "samples": len(row_samples),
            "active_experts": summarize([
                float(sample["active_experts"])
                for sample in row_samples
                if sample["active_experts"] is not None
            ]),
            "scratch_saving_us": summarize([
                sample["xpu_fused_moe_us"] - sample["preallocated_staged_us"]
                for sample in row_samples
            ]),
        }
        for sample_key, _result_key, _required in replay_timing_fields:
            values = [
                float(sample[sample_key])
                for sample in row_samples
                if sample.get(sample_key) is not None
            ]
            if values:
                row_summary[sample_key] = summarize(values)
        if "fused_prologue_offset_gemm_us" in row_summary:
            row_summary["offset_gemm_saving_us"] = summarize([
                sample["xpu_fused_moe_us"] - sample["fused_prologue_offset_gemm_us"]
                for sample in row_samples
                if sample.get("fused_prologue_offset_gemm_us") is not None
            ])
        if "fused_prologue_active_offset_gemm_us" in row_summary:
            row_summary["active_offset_gemm_saving_us"] = summarize([
                sample["xpu_fused_moe_us"] - sample["fused_prologue_active_offset_gemm_us"]
                for sample in row_samples
                if sample.get("fused_prologue_active_offset_gemm_us") is not None
            ])
        by_rows[str(rows)] = row_summary

    return {
        "paths": paths,
        "rows_filter": sorted(rows_filter),
        "sample_count": len(samples),
        "by_rows": by_rows,
        "components_us": {
            name: summarize(values)
            for name, values in components.items()
            if values
        },
        "max_abs_diffs": {
            key: {
                "count": len(values),
                "max": max(values) if values else None,
            }
            for key, values in max_diffs.items()
        },
    }


def collect_gemm_floor(path: str, target_rows: int) -> dict[str, Any]:
    data = load_json(path)
    rows = [
        row for row in data.get("aggregate", [])
        if int(row.get("target_rows", -1)) == target_rows
    ]
    out: dict[str, Any] = {
        "source_path": path,
        "target_rows": target_rows,
    }
    for row in rows:
        stage = row["stage"]
        out[stage] = {
            "mean_us": nested_mean(row, ["mean_us", "mean"]),
            "effective_tops": nested_mean(row, ["effective_tops", "mean"]),
            "cases": int(row.get("cases", 0)),
        }
    if "gemm1" in out and "gemm2" in out:
        out["two_gemm_floor_us"] = out["gemm1"]["mean_us"] + out["gemm2"]["mean_us"]
        out["one_dispatch_floor_proxy_us"] = max(
            out["gemm1"]["mean_us"],
            out["gemm2"]["mean_us"],
        )
    return out


def estimate_decode(
    *,
    current_decode_ms: float,
    layers: int,
    current_layer_us: float,
    candidate_layer_us: float,
) -> dict[str, float]:
    saved_ms = max(0.0, current_layer_us - candidate_layer_us) * layers / 1000.0
    estimated_ms = max(0.001, current_decode_ms - saved_ms)
    return {
        "candidate_layer_us": candidate_layer_us,
        "estimated_saved_ms_per_token": saved_ms,
        "estimated_decode_ms_per_token": estimated_ms,
        "estimated_tok_s": 1000.0 / estimated_ms,
    }


def summary_mean(row: dict[str, Any], key: str) -> float | None:
    summary_row = row.get(key)
    if not isinstance(summary_row, dict):
        return None
    value = summary_row.get("mean")
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    cfg = text_config(args.model_config)
    layers = int(cfg.get("num_hidden_layers", args.num_moe_layers))
    endpoint = endpoint_decode_ms(args.endpoint_metrics_json)
    current_decode_ms = endpoint["decode_ms_per_token"]
    forward_ms = model_forward_ms(args.model_forward_summary_json)
    outside_forward_ms = current_decode_ms - forward_ms
    target_decode_ms = 1000.0 / args.target_tok_s
    target_model_forward_ms = target_decode_ms - outside_forward_ms
    required_model_forward_save_ms = forward_ms - target_model_forward_ms
    required_save_per_layer_us = required_model_forward_save_ms * 1000.0 / layers

    replay = collect_route_replay(args.route_replay_json, set(args.rows))
    row_key = str(args.primary_rows)
    if row_key not in replay["by_rows"]:
        raise ValueError(f"primary rows {args.primary_rows} not found in replay data")
    primary = replay["by_rows"][row_key]
    current_layer_us = primary["xpu_fused_moe_us"]["mean"]
    preallocated_us = primary["preallocated_staged_us"]["mean"]
    fused_prologue_staged_us = summary_mean(primary, "fused_prologue_staged_us")
    offset_gemm_us = summary_mean(primary, "fused_prologue_offset_gemm_us")
    active_offset_gemm_us = summary_mean(primary, "fused_prologue_active_offset_gemm_us")
    gemm_floor = collect_gemm_floor(args.smallm_timing_json, args.primary_rows * args.topk)

    target_layer_us = current_layer_us - required_save_per_layer_us
    scenarios = {
        "current_route_replay": estimate_decode(
            current_decode_ms=current_decode_ms,
            layers=layers,
            current_layer_us=current_layer_us,
            candidate_layer_us=current_layer_us,
        ),
        "preallocated_staged_lower_bound": estimate_decode(
            current_decode_ms=current_decode_ms,
            layers=layers,
            current_layer_us=current_layer_us,
            candidate_layer_us=preallocated_us,
        ),
    }
    for name, value in (
        ("fused_prologue_staged_lower_bound", fused_prologue_staged_us),
        ("fused_prologue_offset_gemm_lower_bound", offset_gemm_us),
        ("fused_prologue_active_offset_gemm_lower_bound", active_offset_gemm_us),
    ):
        if value is not None:
            scenarios[name] = estimate_decode(
                current_decode_ms=current_decode_ms,
                layers=layers,
                current_layer_us=current_layer_us,
                candidate_layer_us=value,
            )
    if "two_gemm_floor_us" in gemm_floor:
        scenarios["two_independent_grouped_gemm_floor"] = estimate_decode(
            current_decode_ms=current_decode_ms,
            layers=layers,
            current_layer_us=current_layer_us,
            candidate_layer_us=gemm_floor["two_gemm_floor_us"],
        )
        scenarios["one_dispatch_floor_proxy"] = estimate_decode(
            current_decode_ms=current_decode_ms,
            layers=layers,
            current_layer_us=current_layer_us,
            candidate_layer_us=gemm_floor["one_dispatch_floor_proxy_us"],
        )
    scenarios["required_for_target"] = estimate_decode(
        current_decode_ms=current_decode_ms,
        layers=layers,
        current_layer_us=current_layer_us,
        candidate_layer_us=target_layer_us,
    )

    return {
        "metadata": {
            "model_config": args.model_config,
            "endpoint_metrics_json": args.endpoint_metrics_json,
            "model_forward_summary_json": args.model_forward_summary_json,
            "route_replay_json": args.route_replay_json,
            "smallm_timing_json": args.smallm_timing_json,
            "target_tok_s": args.target_tok_s,
            "target_decode_ms_per_token": target_decode_ms,
            "num_moe_layers": layers,
            "primary_rows": args.primary_rows,
            "topk": args.topk,
        },
        "endpoint_budget": {
            **endpoint,
            "model_forward_ms_per_token": forward_ms,
            "outside_model_forward_ms_per_token": outside_forward_ms,
            "target_model_forward_ms_per_token_if_outside_unchanged": target_model_forward_ms,
            "required_model_forward_save_ms": required_model_forward_save_ms,
            "required_save_per_moe_layer_us": required_save_per_layer_us,
        },
        "route_replay": replay,
        "primary_layer_budget": {
            "rows": args.primary_rows,
            "current_xpu_fused_moe_us": current_layer_us,
            "preallocated_staged_us": preallocated_us,
            "fused_prologue_staged_us": fused_prologue_staged_us,
            "fused_prologue_offset_gemm_us": offset_gemm_us,
            "fused_prologue_active_offset_gemm_us": active_offset_gemm_us,
            "required_candidate_us_for_target": target_layer_us,
            "required_saving_from_current_us": required_save_per_layer_us,
            "remaining_gap_after_preallocated_us": preallocated_us - target_layer_us,
            "remaining_gap_after_fused_prologue_offset_gemm_us": (
                offset_gemm_us - target_layer_us if offset_gemm_us is not None else None
            ),
            "remaining_gap_after_fused_prologue_active_offset_gemm_us": (
                active_offset_gemm_us - target_layer_us if active_offset_gemm_us is not None else None
            ),
        },
        "grouped_gemm_floor": gemm_floor,
        "decode_scenarios": scenarios,
        "interpretation": [
            "The target is >200 tok/s, or <=5 ms/token decode.",
            "If outside-model-forward time is unchanged, the model-forward bucket must be cut accordingly.",
            "The route replay numbers are single-layer isolated estimates, not endpoint claims.",
            "Offset-GEMM and active-offset-GEMM are exact in isolated replay, but still do not by themselves close the c1 >200 tok/s gap.",
            "Two independent small-M grouped GEMM dispatches already exceed the required per-layer target, so a persistent/fused MoE prototype must avoid paying both dispatch floors.",
            "If a one-dispatch/fused MoE layerlet cannot beat the required candidate budget with exact parity, target-verified speculation becomes the stronger path.",
        ],
    }


def strict_json_value(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: strict_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [strict_json_value(item) for item in value]
    return value


def fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(f):
        return "n/a"
    return f"{f:.{digits}f}"


def write_markdown(path: str, report: dict[str, Any]) -> None:
    meta = report["metadata"]
    budget = report["endpoint_budget"]
    primary = report["primary_layer_budget"]
    floor = report["grouped_gemm_floor"]
    scenarios = report["decode_scenarios"]
    route = report["route_replay"]["by_rows"][str(meta["primary_rows"])]

    lines = []
    lines.append("# Qwen3.6 MoE Fusion Target Budget")
    lines.append("")
    lines.append("## Endpoint Budget")
    lines.append("")
    lines.append(f"- Current decode: `{fmt(budget['decode_ms_per_token'])} ms/token`.")
    lines.append(f"- Current corrected speed: `{fmt(budget['corrected_tok_s'])} tok/s`.")
    lines.append(f"- Model-forward timing: `{fmt(budget['model_forward_ms_per_token'])} ms/token`.")
    lines.append(f"- Outside-forward timing estimate: `{fmt(budget['outside_model_forward_ms_per_token'])} ms/token`.")
    lines.append(f"- Target for `{fmt(meta['target_tok_s'], 0)} tok/s`: `{fmt(meta['target_decode_ms_per_token'])} ms/token`.")
    lines.append(f"- Required model-forward saving if outside cost is unchanged: `{fmt(budget['required_model_forward_save_ms'])} ms/token`.")
    lines.append(f"- Required saving across `{meta['num_moe_layers']}` MoE layers: `{fmt(budget['required_save_per_moe_layer_us'])} us/layer`.")
    lines.append("")
    lines.append("## Primary Route-Replay Layer Budget")
    lines.append("")
    lines.append(f"- Primary rows: `{meta['primary_rows']}` request row, topk `{meta['topk']}` routed rows.")
    lines.append(f"- Route replay samples: `{route['samples']}`.")
    lines.append(f"- Exact current `xpu_fused_moe`: `{fmt(primary['current_xpu_fused_moe_us'])} us/layer`.")
    lines.append(f"- Exact preallocated staged path: `{fmt(primary['preallocated_staged_us'])} us/layer`.")
    lines.append(f"- Exact fused-prologue offset-GEMM path: `{fmt(primary.get('fused_prologue_offset_gemm_us'))} us/layer`.")
    lines.append(f"- Exact fused-prologue active-offset-GEMM path: `{fmt(primary.get('fused_prologue_active_offset_gemm_us'))} us/layer`.")
    lines.append(f"- Candidate layerlet target for >200 tok/s: `{fmt(primary['required_candidate_us_for_target'])} us/layer`.")
    lines.append(f"- Remaining gap after preallocated staged path: `{fmt(primary['remaining_gap_after_preallocated_us'])} us/layer`.")
    lines.append(f"- Remaining gap after offset-GEMM path: `{fmt(primary.get('remaining_gap_after_fused_prologue_offset_gemm_us'))} us/layer`.")
    lines.append(f"- Remaining gap after active-offset-GEMM path: `{fmt(primary.get('remaining_gap_after_fused_prologue_active_offset_gemm_us'))} us/layer`.")
    lines.append("")
    lines.append("## Grouped-GEMM Floor")
    lines.append("")
    lines.append(f"- Floor source target rows: `{floor['target_rows']}`.")
    lines.append(f"- `gemm1`: `{fmt(floor.get('gemm1', {}).get('mean_us'))} us`, `{fmt(floor.get('gemm1', {}).get('effective_tops'))} TOPS`.")
    lines.append(f"- `gemm2`: `{fmt(floor.get('gemm2', {}).get('mean_us'))} us`, `{fmt(floor.get('gemm2', {}).get('effective_tops'))} TOPS`.")
    lines.append(f"- Two independent GEMM floor: `{fmt(floor.get('two_gemm_floor_us'))} us`.")
    lines.append(f"- One-dispatch floor proxy: `{fmt(floor.get('one_dispatch_floor_proxy_us'))} us`.")
    lines.append("")
    lines.append("## Decode Scenarios")
    lines.append("")
    lines.append("| scenario | layer us | saved ms/token | est decode ms | est tok/s |")
    lines.append("|---|---:|---:|---:|---:|")
    for name, row in scenarios.items():
        lines.append(
            f"| `{name}` | {fmt(row['candidate_layer_us'])} | "
            f"{fmt(row['estimated_saved_ms_per_token'])} | "
            f"{fmt(row['estimated_decode_ms_per_token'])} | "
            f"{fmt(row['estimated_tok_s'])} |"
        )
    lines.append("")
    lines.append("## Decision")
    lines.append("")
    lines.append("- The next fused/persistent MoE layerlet must target roughly "
                 f"`{fmt(primary['required_candidate_us_for_target'])} us` "
                 f"or better for rows=`{meta['primary_rows']}` while matching "
                 "`xpu_fused_moe` numerically.")
    lines.append("- Two separate small-M grouped GEMM dispatches already exceed that budget.")
    lines.append("- A viable non-speculative kernel needs one resident/fused dispatch boundary for route/remap, quant, GEMM1, activation, quant2, GEMM2, and gather, or a comparable way to amortize the fixed dispatch floor.")
    lines.append("- If that cannot be shown in one-layer replay, the next >200 tok/s path should shift to exact target-verified speculation.")
    lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def parse_rows(value: str) -> list[int]:
    rows = []
    for item in value.split(","):
        item = item.strip()
        if item:
            rows.append(int(item))
    if not rows:
        raise argparse.ArgumentTypeError("expected at least one row count")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-config", default=DEFAULT_MODEL_CONFIG)
    parser.add_argument("--endpoint-metrics-json", required=True)
    parser.add_argument("--model-forward-summary-json", required=True)
    parser.add_argument("--route-replay-json", nargs="+", required=True)
    parser.add_argument("--smallm-timing-json", required=True)
    parser.add_argument("--target-tok-s", type=float, default=200.0)
    parser.add_argument("--num-moe-layers", type=int, default=40)
    parser.add_argument("--rows", type=parse_rows, default=parse_rows("1,16"))
    parser.add_argument("--primary-rows", type=int, default=1)
    parser.add_argument("--topk", type=int, default=8)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--markdown-out")
    args = parser.parse_args()

    report = build_report(args)
    Path(args.output_json).write_text(
        json.dumps(strict_json_value(report), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.markdown_out:
        write_markdown(args.markdown_out, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
