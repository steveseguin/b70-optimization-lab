#!/usr/bin/env python3
"""Build a compact Qwen3.6 c1 forward-bottleneck decision artifact."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any


DEFAULT_INPUTS = {
    "gap_budget": "data/qwen36-c1-gap-budget-fullcandidate-20260613h.json",
    "tail_check": "data/qwen36-quark-int8-tp4-tailcheck-latency-decomp-20260613l.json",
    "forward_boundary": "data/qwen36-quark-int8-tp4-allrank-forwardboundary-summary-20260612cj.json",
    "rankmap_reversal": "data/qwen36-quark-int8-tp4-allrank-forwardboundary-rankmap-rev-summary-20260612cl.json",
    "engine_allrank": "data/qwen36-quark-int8-tp4-engine-allrank-timing-summary-20260612br.json",
    "rpc_fastoutput": "data/qwen36-quark-int8-tp4-rpc-fastoutput-summary-20260612bu.json",
    "async_output_reuse": "data/qwen36-quark-int8-tp4-async-output-reuse-timing-summary-20260612bw.json",
    "presampler_forward": "data/qwen36-quark-int8-tp4-presampler-forwardboundary-nested-summary-20260612ci.json",
    "gemma_dashboard": "data/gemma-dashboard-results-summary-20260613k.json",
}


LABELS_OF_INTEREST = [
    "gpu_model_runner.model_forward",
    "gdn_attention_core_xpu.native",
    "gpu_model_runner.postprocess_total",
    "gpu_model_runner.compute_logits",
    "gpu_model_runner.sample_total",
    "gpu_model_runner.sampler",
    "gpu_model_runner.async_output_wrap",
]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def get_path(data: Any, path: list[Any], default: Any = None) -> Any:
    cur = data
    for key in path:
        if isinstance(cur, dict):
            cur = cur.get(key, default)
        elif isinstance(cur, list) and isinstance(key, int):
            cur = cur[key] if len(cur) > key else default
        else:
            return default
    return cur


def label_means(summary: dict[str, Any]) -> dict[str, float]:
    rows = get_path(summary, ["step_summary_by_bucket"], [])
    if not rows:
        return {}
    labels = get_path(rows[0], ["top_labels_by_mean_total_ms"], [])
    out: dict[str, float] = {}
    for row in labels:
        label = row.get("label")
        if label in LABELS_OF_INTEREST:
            out[label] = row.get("mean_total_ms")
    return out


def rank_forward_means(summary: dict[str, Any]) -> dict[str, float]:
    rows = summary.get("pure_decode_after_first5_each_rank_by_rank") or {}
    out: dict[str, float] = {}
    for rank, metrics in rows.items():
        mean = get_path(metrics, ["forward_end_after_start_sync_ms", "mean"])
        if mean is not None:
            out[str(rank)] = mean
    return out


def rank_spread_ms(means: dict[str, float]) -> float | None:
    if not means:
        return None
    vals = list(means.values())
    return max(vals) - min(vals)


def build_decision(repo: Path) -> dict[str, Any]:
    inputs = {name: str(repo / rel) for name, rel in DEFAULT_INPUTS.items()}
    data = {name: read_json(Path(path)) for name, path in inputs.items()}

    gap = data["gap_budget"]["budget"]
    tail = data["tail_check"]
    forward = data["forward_boundary"]
    rankmap = data["rankmap_reversal"]
    presampler = data["presampler_forward"]
    gemma = data["gemma_dashboard"]

    profiles = {
        "engine_allrank": label_means(data["engine_allrank"]),
        "rpc_fastoutput": label_means(data["rpc_fastoutput"]),
        "async_output_reuse": label_means(data["async_output_reuse"]),
    }

    model_forward_values = [
        labels["gpu_model_runner.model_forward"]
        for labels in profiles.values()
        if "gpu_model_runner.model_forward" in labels
    ]
    gdn_values = [
        labels["gdn_attention_core_xpu.native"]
        for labels in profiles.values()
        if "gdn_attention_core_xpu.native" in labels
    ]

    unrotated_rank_means = rank_forward_means(forward)
    reversed_rank_means = rank_forward_means(rankmap)

    tail_stream_match_pct = get_path(
        tail, ["comparisons", "backend_stream_client_vs_vllm_decode_pct"]
    )
    nonstream_delta_pct = get_path(
        tail, ["comparisons", "backend_nonstream_e2e_vs_backend_stream_corrected_pct"]
    )
    queue_stream_ms = get_path(
        tail, ["scenarios", "backend_stream", "metrics", "vllm_queue_ms"]
    )
    queue_nonstream_ms = get_path(
        tail, ["scenarios", "backend_nonstream", "metrics", "vllm_queue_ms"]
    )

    return {
        "created_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "model": data["gap_budget"]["model"],
        "source_inputs": DEFAULT_INPUTS,
        "goal": {
            "target_tok_s": gap["target_tok_s"],
            "target_ms_per_token": gap["target_ms_per_token"],
            "current_best_tok_s": tail["current_best_tok_s"],
            "current_best_ms_per_token": tail["current_best_ms_per_token"],
            "required_ms_saving_per_token": tail["current_best_ms_per_token"] - gap["target_ms_per_token"],
            "required_latency_reduction_pct": tail["ms_per_token_reduction_needed_pct"],
        },
        "decision": {
            "primary_bottleneck": "model_forward_or_forward_stream_dependencies",
            "next_implementation_target": "route-signature overlay plus persistent one-dispatch MoE layerlet prototype",
            "backup_target": "oracle k=1 verifier/KV repair for exact multi-token acceptance",
            "deprioritized": [
                "HTTP/SSE/frontdoor/response packaging for c1 decode",
                "detokenization-only changes as a 2x lever",
                "static lm-head/logits restriction before timing proves it matters",
                "physical-card-only topology tuning as the lead hypothesis",
            ],
        },
        "evidence": {
            "tail_check": {
                "stream_client_vs_vllm_decode_pct": tail_stream_match_pct,
                "nonstream_e2e_vs_stream_corrected_pct": nonstream_delta_pct,
                "queue_ms": {
                    "stream": queue_stream_ms,
                    "nonstream": queue_nonstream_ms,
                },
                "interpretation": "client stream timing tracks vLLM decode and queue is effectively zero",
            },
            "forward_boundary": {
                "unrotated_allrank_forward_start_mean_ms": get_path(
                    forward, ["pure_decode_after_first5_each_rank", "forward_start_sync_ms", "mean"]
                ),
                "unrotated_allrank_forward_end_mean_ms": get_path(
                    forward, ["pure_decode_after_first5_each_rank", "forward_end_after_start_sync_ms", "mean"]
                ),
                "unrotated_rank_forward_end_mean_ms": unrotated_rank_means,
                "unrotated_rank_spread_ms": rank_spread_ms(unrotated_rank_means),
                "rankmap_reversed_rank_to_physical_device": rankmap.get("rank_to_physical_device_id"),
                "rankmap_reversed_rank_forward_end_mean_ms": reversed_rank_means,
                "rankmap_reversed_rank_spread_ms": rank_spread_ms(reversed_rank_means),
                "presampler_forward_end_mean_ms": get_path(
                    presampler,
                    [
                        "pure_decode_after_first5",
                        "pre_sampler_stage_sync_ms",
                        "forward_end",
                        "mean",
                    ],
                ),
                "presampler_forward_start_mean_ms": get_path(
                    presampler,
                    [
                        "pure_decode_after_first5",
                        "pre_sampler_stage_sync_ms",
                        "forward_start",
                        "mean",
                    ],
                ),
                "interpretation": "forward_start sync is near-zero, while forward_end carries multi-ms wait on all ranks",
            },
            "engine_profiles": {
                "label_mean_ms_by_profile": profiles,
                "model_forward_mean_ms_range": [
                    min(model_forward_values),
                    max(model_forward_values),
                ],
                "gdn_attention_mean_ms_range": [
                    min(gdn_values),
                    max(gdn_values),
                ],
                "interpretation": "logits, sampler, and async-output labels remain sub-ms while model-forward dominates measured worker time",
            },
            "gemma_dashboard_source_check": {
                "count": gemma["count"],
                "top_tps": get_path(gemma, ["top_tps", 0, "tps"]),
                "top_method": get_path(gemma, ["top_tps", 0, "method"]),
                "keyword_counts": gemma["keyword_counts"],
                "transfer": "stable methodology signal: captured decode, exact fallback lanes, warm artifacts, negative-result hygiene",
            },
        },
        "next_steps": [
            "Add rank/layer route-signature overlay to the all-rank forward-boundary probe.",
            "Split model-forward timing by layer family on slow ranks: attention, router, expert gather, expert GEMM, combine, collectives.",
            "Prototype a persistent or route-class one-dispatch MoE layerlet only after the route overlay identifies stable hot classes.",
            "Keep output-tail and lm-head experiments as secondary until the new layer-family trace shows they are material.",
        ],
    }


def write_markdown(decision: dict[str, Any], path: Path) -> None:
    goal = decision["goal"]
    evidence = decision["evidence"]
    lines = [
        "# Qwen3.6 Forward Bottleneck Decision 20260613m",
        "",
        "This is a decision artifact, not a new speed benchmark.",
        "",
        "## Target Gap",
        "",
        f"- Current clean c1 decode: `{goal['current_best_tok_s']:.3f} tok/s` (`{goal['current_best_ms_per_token']:.3f} ms/token`).",
        f"- Target: `{goal['target_tok_s']:.1f} tok/s` (`{goal['target_ms_per_token']:.3f} ms/token`).",
        f"- Required saving: `{goal['required_ms_saving_per_token']:.3f} ms/token` (`{goal['required_latency_reduction_pct']:.2f}%`).",
        "",
        "## Decision",
        "",
        f"- Primary bottleneck: `{decision['decision']['primary_bottleneck']}`.",
        f"- Next implementation target: `{decision['decision']['next_implementation_target']}`.",
        f"- Backup target: `{decision['decision']['backup_target']}`.",
        "",
        "Deprioritized as lead levers:",
    ]
    for item in decision["decision"]["deprioritized"]:
        lines.append(f"- {item}.")

    tail = evidence["tail_check"]
    fb = evidence["forward_boundary"]
    engine = evidence["engine_profiles"]
    gemma = evidence["gemma_dashboard_source_check"]
    lines += [
        "",
        "## Evidence",
        "",
        f"- Tail check: stream client vs vLLM decode differs by `{tail['stream_client_vs_vllm_decode_pct']:.3f}%`; queue is `{tail['queue_ms']['stream']:.4f}-{tail['queue_ms']['nonstream']:.4f} ms`.",
        f"- Forward boundary: start sync mean is `{fb['unrotated_allrank_forward_start_mean_ms']:.6f} ms`, while forward-end wait mean is `{fb['unrotated_allrank_forward_end_mean_ms']:.3f} ms`.",
        f"- Rank reversal: TP0 stayed fastest after moving to physical card `{fb['rankmap_reversed_rank_to_physical_device']['0']}`; rank spread remained `{fb['rankmap_reversed_rank_spread_ms']:.3f} ms`.",
        f"- Presampler split: forward-end sync mean is `{fb['presampler_forward_end_mean_ms']:.3f} ms`; forward-start sync mean is `{fb['presampler_forward_start_mean_ms']:.6f} ms`.",
        f"- Worker labels: model-forward mean range is `{engine['model_forward_mean_ms_range'][0]:.3f}-{engine['model_forward_mean_ms_range'][1]:.3f} ms`; GDN attention mean range is `{engine['gdn_attention_mean_ms_range'][0]:.3f}-{engine['gdn_attention_mean_ms_range'][1]:.3f} ms`.",
        f"- Gemma dashboard source check: latest tracked snapshot has `{gemma['count']}` rows and the same `{gemma['top_tps']:.3f} tok/s` top method `{gemma['top_method']}`; use it only for methodology transfer.",
        "",
        "## Next Steps",
        "",
    ]
    for item in decision["next_steps"]:
        lines.append(f"- {item}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--md-out", required=True)
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    decision = build_decision(repo)
    json_path = repo / args.json_out
    md_path = repo / args.md_out
    json_path.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(decision, md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
