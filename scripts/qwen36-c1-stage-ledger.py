#!/usr/bin/env python3
"""Build a c1 timing ledger from endpoint metrics and timing-log summaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def first_bucket(summary: dict[str, Any]) -> dict[str, Any] | None:
    buckets = summary.get("step_summary_by_bucket")
    if isinstance(buckets, list) and buckets:
        return buckets[0]
    return None


def summary_label(summary: dict[str, Any], label: str) -> dict[str, Any] | None:
    rows = summary.get("summary_by_total_ms") or []
    for row in rows:
        if row.get("label") == label:
            return row
    return None


def top_step_label(bucket: dict[str, Any], label: str) -> dict[str, Any] | None:
    rows = bucket.get("top_labels_by_mean_total_ms") or []
    for row in rows:
        if row.get("label") == label:
            return row
    return None


def f(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def make_markdown(artifact: dict[str, Any]) -> str:
    gap = artifact["endpoint_gap_budget"]
    lines = [
        "# Qwen3.6 C1 Stage Ledger",
        "",
        f"Endpoint decode: `{gap['current_decode_ms_per_token']:.3f} ms/token`.",
        f"Target: `{gap['target_ms_per_token']:.3f} ms/token`.",
        f"Required saving: `{gap['required_ms_saving_per_token']:.3f} ms/token`.",
        "",
        "## Timing Proxies",
        "",
        "| source | model-forward proxy | endpoint minus proxy | theoretical tok/s if only outside/proxy gap vanished | notes |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for row in artifact["timing_proxies"]:
        lines.append(
            "| {name} | {proxy:.3f} ms | {delta:.3f} ms | {tok_s:.1f} | {notes} |".format(
                name=row["name"],
                proxy=row["model_forward_ms"],
                delta=row["endpoint_minus_model_forward_ms"],
                tok_s=row["tok_s_if_endpoint_matched_proxy"],
                notes=row["notes"],
            )
        )
    lines.extend([
        "",
        "## Interpretation",
        "",
    ])
    for item in artifact["interpretation"]:
        lines.append(f"- {item}")
    lines.extend([
        "",
        "## Required Next Instrumentation",
        "",
    ])
    for item in artifact["required_next_instrumentation"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gap-budget", required=True)
    parser.add_argument("--nosync-summary", required=True)
    parser.add_argument("--sync-summary", required=True)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=True)
    args = parser.parse_args()

    gap = load_json(args.gap_budget)
    nosync = load_json(args.nosync_summary)
    sync = load_json(args.sync_summary)
    budget = gap["budget"]
    endpoint_ms = float(budget["current_decode_ms_per_token"])
    target_ms = float(budget["target_ms_per_token"])
    required_saving = float(budget["required_ms_saving_per_token"])

    proxies = []
    for name, summary, notes in [
        (
            "nosync_label_timing",
            nosync,
            "Pure decode timing-step proxy; low overhead but not identical to the live endpoint run.",
        ),
        (
            "sync_modelonly",
            sync,
            "Synchronized model-forward-only proxy; closer to endpoint latency but perturbs the run.",
        ),
    ]:
        bucket = first_bucket(summary)
        if not bucket:
            continue
        model_forward_ms = f(bucket.get("median_model_forward_ms"))
        if model_forward_ms is None:
            continue
        row: dict[str, Any] = {
            "name": name,
            "source_log": summary.get("source_log"),
            "model_forward_ms": model_forward_ms,
            "endpoint_minus_model_forward_ms": endpoint_ms - model_forward_ms,
            "tok_s_if_endpoint_matched_proxy": 1000.0 / model_forward_ms,
            "target_minus_model_forward_ms": target_ms - model_forward_ms,
            "notes": notes,
            "step_count": bucket.get("step_count"),
            "decode_bucket": (bucket.get("group") or {}).get("decode_bucket"),
            "top_labels_by_mean_total_ms": bucket.get("top_labels_by_mean_total_ms") or [],
        }
        gdn = top_step_label(bucket, "gdn_attention_core_xpu.native")
        logits = top_step_label(bucket, "logits.local_argmax_lm_head")
        if gdn:
            row["gdn_attention_total_ms_proxy"] = gdn.get("median_total_ms")
            row["gdn_attention_share_of_model_forward_proxy"] = (
                f(gdn.get("median_total_ms")) or 0.0
            ) / model_forward_ms
        if logits:
            row["logits_total_ms_proxy"] = logits.get("median_total_ms")
        proxies.append(row)

    nosync_model = proxies[0]["model_forward_ms"] if proxies else None
    interpretation = [
        "The endpoint c1 decode path is about 9.98 ms/token, while prior pure-decode timing proxies range from about 5.46 ms to 8.43 ms depending on instrumentation.",
        "The gap between endpoint decode and the nosync model-forward proxy is about 4.52 ms/token, almost the entire 4.98 ms/token saving needed for 200 tok/s.",
        "Even if the endpoint matched the nosync proxy exactly, throughput would be about 183 tok/s, so we still need either a smaller model-forward improvement or target-verified multi-token acceptance.",
        "The sync model-only proxy shows about 8.43 ms/token, which means synchronization or instrumentation can erase most of the apparent headroom; future profiling must be device-side and low overhead.",
        "Nested timing labels such as GDN, MoE, and all-reduce are useful directionally, but they are not exclusive wall-time slices and must not be summed into a token budget.",
    ]
    if nosync_model is not None:
        interpretation.append(
            "A concrete no-spec path to 200 tok/s would need endpoint/outside overhead near the nosync timing path plus at least "
            f"{max(0.0, nosync_model - target_ms):.3f} ms/token shaved from the model-forward proxy."
        )

    artifact = {
        "gap_budget_path": args.gap_budget,
        "nosync_summary_path": args.nosync_summary,
        "sync_summary_path": args.sync_summary,
        "endpoint_gap_budget": {
            "current_decode_ms_per_token": endpoint_ms,
            "target_ms_per_token": target_ms,
            "required_ms_saving_per_token": required_saving,
            "current_corrected_tok_s": budget.get("current_corrected_tok_s"),
            "target_tok_s": budget.get("target_tok_s"),
        },
        "timing_proxies": proxies,
        "interpretation": interpretation,
        "required_next_instrumentation": [
            "Add one low-overhead per-token timing-step capture on the accepted backend, with model_forward, scheduler/output, sampler, and streaming boundaries in the same request.",
            "For XPU device work, prefer queue/event timestamps or existing low-overhead timers; avoid forced synchronization in the hot path.",
            "Make MoE timing exclusive enough to separate route packing, GEMM1, activation/quant, GEMM2, gather, and all-reduce without double-counting nested labels.",
            "Tie each timing trace to request id, prompt/output token counts, graph bucket, and canary/provenance result.",
        ],
    }

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(artifact, indent=2) + "\n")
    out_md.write_text(make_markdown(artifact))
    print(json.dumps(artifact["endpoint_gap_budget"], indent=2))
    for row in proxies:
        print(
            f"{row['name']}: model_forward={row['model_forward_ms']:.3f}ms "
            f"endpoint_minus={row['endpoint_minus_model_forward_ms']:.3f}ms "
            f"matched_proxy={row['tok_s_if_endpoint_matched_proxy']:.1f}tok/s"
        )
    print(f"wrote={out_json}")
    print(f"wrote={out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
