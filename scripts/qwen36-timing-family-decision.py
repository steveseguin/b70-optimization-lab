#!/usr/bin/env python3
"""Classify a fresh Qwen3.6 XPU decode timing summary by bottleneck family.

This script intentionally does not claim exclusive wall time. The XPU timing
labels are nested and some are wrappers, so the decision uses family-ranked
top labels and rank skew as a routing signal for the next experiment.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any


FAMILY_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    (
        "moe",
        (
            "moe.",
            "moe_",
            "xpu_moe.",
            "qwen3_next.moe",
            "qwen3_next.layer.mlp",
            "qwen3_next.moe.experts",
        ),
    ),
    (
        "gdn",
        (
            "qwen3_next.gdn",
            "gdn_attention_core",
            "qwen3_next.layer.linear_attention",
        ),
    ),
    (
        "full_attention",
        (
            "qwen3_next.full_attention",
            "qwen3_next.layer.full_attention",
            "qwen3_next.layer_type.full_attention",
        ),
    ),
    (
        "collectives",
        (
            "all_reduce",
            "all_gather",
            "allgather",
            "reduce_scatter",
            "reduce_scatterv",
            "broadcast",
            "collective",
        ),
    ),
    (
        "logits_sampler",
        (
            "logits.",
            "gpu_model_runner.compute_logits",
            "gpu_model_runner.sampler",
            "gpu_model_runner.sample_total",
            "gpu_model_runner.select_sample_hidden",
            "gpu_model_runner.clone_sample_hidden",
        ),
    ),
    (
        "runtime",
        (
            "gpu_model_runner.preprocess",
            "gpu_model_runner.postprocess",
            "gpu_model_runner.async_output",
            "gpu_model_runner.bookkeeping",
            "gpu_model_runner.forward_total",
            "worker_",
            "executor_",
        ),
    ),
]

WRAPPER_LABELS = {
    "gpu_model_runner.model_forward",
    "gpu_model_runner.forward_total",
    "gpu_model_runner.preprocess_total",
    "gpu_model_runner.sample_total",
    "gpu_model_runner.postprocess_total",
    "qwen3_next.final_norm",
}

TARGET_BY_FAMILY = {
    "moe": "persistent_w8a8_moe_layerlet",
    "gdn": "gdn_dense_w8a8_quant_gemm_fusion",
    "full_attention": "full_attention_projection_or_collective_boundary",
    "collectives": "collective_replay_topology_or_tp_layout",
    "logits_sampler": "logits_sampler_or_local_argmax_boundary",
    "runtime": "scheduler_runtime_static_c1_lane",
}


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def f(value: Any) -> float | None:
    try:
        if value is None:
            return None
        value_f = float(value)
    except (TypeError, ValueError):
        return None
    return value_f if math.isfinite(value_f) else None


def nested(data: Any, keys: list[str]) -> Any:
    cur = data
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def family_for_label(label: str) -> str:
    lower = label.lower()
    for family, needles in FAMILY_PATTERNS:
        if any(needle.lower() in lower for needle in needles):
            return family
    if label.startswith("gpu_model_runner."):
        return "runtime"
    return "other"


def metric_from_row(row: dict[str, Any]) -> float | None:
    for key in (
        "mean_total_ms_per_step",
        "median_total_ms_per_step",
        "avg_ms",
        "mean_avg_ms_per_call",
    ):
        value = f(row.get(key))
        if value is not None:
            return value
    return None


def collect_label_rows(summary: dict[str, Any], source: str) -> list[dict[str, Any]]:
    if source == "step_rank":
        rows = summary.get("step_summary_by_rank_label")
        return rows if isinstance(rows, list) else []
    if source == "step":
        rows = summary.get("step_summary_by_mean_total_ms")
        return rows if isinstance(rows, list) else []
    if source == "aggregate":
        rows = summary.get("summary_by_total_ms")
        return normalize_aggregate_rows(rows) if isinstance(rows, list) else []
    return []


def normalize_aggregate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert process-exit aggregate rows into approximate per-step rows.

    The raw aggregate summary has one row per rank/label with total wall time and
    call count. Per-call ranking is misleading for repeated layer labels such as
    MoE. Normalize total_ms by the model-forward count on the same rank so the
    classifier sees an approximate per-decode-step contribution.
    """

    step_counts: dict[str, int] = {}
    for row in rows:
        label = str(row.get("label") or "")
        if label != "gpu_model_runner.model_forward":
            continue
        rank = str(row.get("rank", ""))
        try:
            count = int(row.get("count") or 0)
        except (TypeError, ValueError):
            count = 0
        if count > 0:
            step_counts[rank] = count

    out: list[dict[str, Any]] = []
    for row in rows:
        rank = str(row.get("rank", ""))
        total_ms = f(row.get("total_ms"))
        count = step_counts.get(rank)
        copied = dict(row)
        if total_ms is not None and count:
            copied["mean_total_ms_per_step"] = total_ms / count
            copied["aggregate_normalized_by_model_forward_count"] = count
        out.append(copied)
    return out


def summarize_labels(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        label = str(row.get("label") or "")
        if not label:
            continue
        value = metric_from_row(row)
        if value is None:
            continue
        grouped.setdefault(label, []).append({**row, "_metric_ms": value})

    labels: dict[str, dict[str, Any]] = {}
    for label, items in grouped.items():
        metrics = [float(item["_metric_ms"]) for item in items]
        ranks = sorted({str(item.get("rank", "")) for item in items})
        labels[label] = {
            "label": label,
            "family": family_for_label(label),
            "row_count": len(items),
            "rank_count": len([rank for rank in ranks if rank != ""]),
            "mean_ms": statistics.fmean(metrics),
            "median_ms": statistics.median(metrics),
            "max_ms": max(metrics),
            "min_ms": min(metrics),
            "rank_skew_ms": max(metrics) - min(metrics) if len(metrics) > 1 else 0.0,
            "is_wrapper": label in WRAPPER_LABELS,
        }
    return labels


def summarize_families(labels: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    families: dict[str, list[dict[str, Any]]] = {}
    for item in labels.values():
        if item["is_wrapper"]:
            continue
        families.setdefault(item["family"], []).append(item)

    out: dict[str, dict[str, Any]] = {}
    for family, items in families.items():
        items_sorted = sorted(items, key=lambda row: row["max_ms"], reverse=True)
        out[family] = {
            "label_count": len(items_sorted),
            "top_label": items_sorted[0]["label"] if items_sorted else None,
            "top_label_max_ms": items_sorted[0]["max_ms"] if items_sorted else 0.0,
            "top_label_rank_skew_ms": items_sorted[0]["rank_skew_ms"] if items_sorted else 0.0,
            "top_labels": [
                {
                    "label": item["label"],
                    "max_ms": item["max_ms"],
                    "mean_ms": item["mean_ms"],
                    "rank_skew_ms": item["rank_skew_ms"],
                }
                for item in items_sorted[:12]
            ],
            "nonexclusive_sum_max_ms": sum(item["max_ms"] for item in items_sorted),
        }
    return out


def metrics_summary(metrics: dict[str, Any] | None) -> dict[str, Any]:
    if not metrics:
        return {}
    summary = metrics.get("summary") if isinstance(metrics, dict) else None
    if not isinstance(summary, dict):
        return {}
    return {
        "tok_s_out_client_after_first_chunk_corrected_mean": nested(
            summary, ["tok_s_out_client_after_first_chunk_corrected", "mean"]
        ),
        "decode_ms_per_generation_token_vllm_mean": nested(
            summary, ["decode_ms_per_generation_token_vllm_histogram", "mean"]
        ),
        "ttft_ms_mean": nested(summary, ["ttft_ms", "mean"]),
    }


def choose_target(families: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ranked = sorted(
        (
            {
                "family": family,
                "score_ms": data.get("top_label_max_ms", 0.0),
                "top_label": data.get("top_label"),
                "rank_skew_ms": data.get("top_label_rank_skew_ms", 0.0),
            }
            for family, data in families.items()
            if family != "other"
        ),
        key=lambda row: row["score_ms"],
        reverse=True,
    )
    if not ranked:
        return {
            "family": "unknown",
            "next_target": "manual_trace_inspection",
            "reason": "no classified timing labels found",
        }
    winner = ranked[0]
    runner_up = ranked[1] if len(ranked) > 1 else None
    target = TARGET_BY_FAMILY.get(winner["family"], "manual_trace_inspection")
    reason = (
        f"{winner['family']} has the largest visible per-family label "
        f"({winner['top_label']} at {winner['score_ms']:.6f} ms)."
    )
    if runner_up:
        reason += (
            f" Runner-up is {runner_up['family']} at "
            f"{runner_up['score_ms']:.6f} ms."
        )
    return {
        **winner,
        "next_target": target,
        "runner_up": runner_up,
        "reason": reason,
    }


def has_model_family_signal(families: dict[str, dict[str, Any]]) -> bool:
    for family in ("moe", "gdn", "full_attention", "collectives", "logits_sampler"):
        if families.get(family, {}).get("top_label_max_ms", 0.0) > 0.0:
            return True
    return False


def write_markdown(payload: dict[str, Any], path: Path) -> None:
    decision = payload["decision"]
    lines = [
        "# Qwen3.6 Timing Family Decision",
        "",
        "This is a routing artifact, not a speed claim. Timing labels are nested;",
        "family sums are non-exclusive.",
        "",
        "## Decision",
        "",
        f"- Next target: `{decision['next_target']}`.",
        f"- Leading family: `{decision['family']}`.",
        f"- Decision basis: `{payload['decision_basis']}`.",
        f"- Reason: {decision['reason']}",
    ]
    endpoint = payload.get("endpoint_metrics") or {}
    if endpoint:
        lines.extend(
            [
                "",
                "## Endpoint Metrics",
                "",
                f"- Corrected output tok/s: `{endpoint.get('tok_s_out_client_after_first_chunk_corrected_mean')}`.",
                f"- vLLM decode ms/token: `{endpoint.get('decode_ms_per_generation_token_vllm_mean')}`.",
                f"- TTFT ms: `{endpoint.get('ttft_ms_mean')}`.",
            ]
        )
    lines.extend(["", "## Family Ranking", ""])
    for family, data in payload["families_ranked"]:
        lines.append(
            f"- `{family}`: top `{data.get('top_label')}` "
            f"max `{data.get('top_label_max_ms'):.6f}` ms, "
            f"rank skew `{data.get('top_label_rank_skew_ms'):.6f}` ms."
        )
    lines.extend(["", "## Top Labels", ""])
    for label in payload["top_labels"][:20]:
        lines.append(
            f"- `{label['label']}` ({label['family']}): "
            f"max `{label['max_ms']:.6f}` ms, mean `{label['mean_ms']:.6f}` ms, "
            f"rank skew `{label['rank_skew_ms']:.6f}` ms."
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", required=True, help="summarize-xpu-decode-timing-log JSON")
    parser.add_argument("--metrics", help="measure-openai-endpoint-metrics JSON")
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=True)
    args = parser.parse_args()

    summary = load_json(args.summary)
    metrics = load_json(args.metrics) if args.metrics else None

    aggregate_labels = summarize_labels(collect_label_rows(summary, "aggregate"))
    step_rank_labels = summarize_labels(collect_label_rows(summary, "step_rank"))
    step_labels = summarize_labels(collect_label_rows(summary, "step"))
    aggregate_families = summarize_families(aggregate_labels)
    step_rank_families = summarize_families(step_rank_labels)
    step_families = summarize_families(step_labels)

    if has_model_family_signal(aggregate_families):
        decision_basis = "aggregate_exit_summary"
        labels = aggregate_labels
        families = aggregate_families
    elif has_model_family_signal(step_rank_families):
        decision_basis = "step_rank_summary"
        labels = step_rank_labels
        families = step_rank_families
    else:
        decision_basis = "step_summary"
        labels = step_labels
        families = step_families

    decision = choose_target(families)
    top_labels = sorted(labels.values(), key=lambda row: row["max_ms"], reverse=True)
    families_ranked = sorted(
        families.items(),
        key=lambda item: item[1].get("top_label_max_ms", 0.0),
        reverse=True,
    )
    payload = {
        "summary_path": args.summary,
        "metrics_path": args.metrics,
        "source_log": summary.get("source_log"),
        "endpoint_metrics": metrics_summary(metrics),
        "decision_basis": decision_basis,
        "decision": decision,
        "families": families,
        "families_ranked": families_ranked,
        "top_labels": top_labels,
        "views": {
            "aggregate_exit_summary": {
                "families": aggregate_families,
                "top_labels": sorted(
                    aggregate_labels.values(),
                    key=lambda row: row["max_ms"],
                    reverse=True,
                )[:40],
            },
            "step_rank_summary": {
                "families": step_rank_families,
                "top_labels": sorted(
                    step_rank_labels.values(),
                    key=lambda row: row["max_ms"],
                    reverse=True,
                )[:40],
            },
            "step_summary": {
                "families": step_families,
                "top_labels": sorted(
                    step_labels.values(),
                    key=lambda row: row["max_ms"],
                    reverse=True,
                )[:40],
            },
        },
        "warning": "Timing labels are nested and non-exclusive; use this as a routing signal only.",
    }

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(payload, out_md)
    print(json.dumps(decision, indent=2, sort_keys=True))
    print(f"wrote={out_json}")
    print(f"wrote={out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
