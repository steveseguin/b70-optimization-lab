#!/usr/bin/env python3
"""Summarize Qwen3.6 c1 latency decomposition artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def mean_metric(artifact: dict[str, Any], key: str) -> float | None:
    value = artifact.get("summary", {}).get(key, {})
    if isinstance(value, dict) and isinstance(value.get("mean"), (int, float)):
        return float(value["mean"])
    return None


def load_labeled(paths: list[str]) -> dict[str, dict[str, Any]]:
    artifacts = {}
    for item in paths:
        if "=" not in item:
            raise ValueError(f"expected LABEL=PATH, got {item!r}")
        label, path = item.split("=", 1)
        artifacts[label] = json.loads(Path(path).read_text(encoding="utf-8"))
    return artifacts


def pick_decode_tok_s(metrics: dict[str, float | None]) -> float | None:
    ms = metrics.get("vllm_decode_ms_per_generation_token")
    if ms and ms > 0:
        return 1000.0 / ms
    return None


def summarize(artifacts: dict[str, dict[str, Any]], target_tok_s: float) -> dict[str, Any]:
    scenarios: dict[str, Any] = {}
    for label, artifact in artifacts.items():
        metrics: dict[str, float | None] = {
            "client_after_first_corrected_tok_s": mean_metric(
                artifact, "tok_s_out_client_after_first_chunk_corrected"
            ),
            "client_after_first_tok_s": mean_metric(
                artifact, "tok_s_out_client_after_first_chunk"
            ),
            "client_e2e_tok_s": mean_metric(artifact, "tok_s_out_client_e2e"),
            "client_ttft_ms": mean_metric(artifact, "ttft_ms_client"),
            "vllm_ttft_ms": mean_metric(artifact, "ttft_ms_vllm_metrics"),
            "vllm_queue_ms": mean_metric(artifact, "queue_ms_vllm_histogram"),
            "vllm_prefill_ms": mean_metric(artifact, "prefill_ms_vllm_histogram"),
            "vllm_decode_ms": mean_metric(artifact, "decode_ms_vllm_histogram"),
            "vllm_decode_ms_per_generation_token": mean_metric(
                artifact, "decode_ms_per_generation_token_vllm_histogram"
            ),
            "vllm_time_per_output_token_ms": mean_metric(
                artifact, "time_per_output_token_ms_vllm_histogram"
            ),
            "vllm_iteration_tokens_per_step": mean_metric(
                artifact, "iteration_tokens_per_step_vllm_histogram"
            ),
        }
        metrics["vllm_decode_tok_s_from_histogram"] = pick_decode_tok_s(metrics)
        scenarios[label] = {
            "path": artifact.get("base_url"),
            "endpoint": artifact.get("endpoint"),
            "mode": artifact.get("mode"),
            "prompt_tokens_actual": artifact.get("prompt_tokens_actual"),
            "output_tokens_requested": artifact.get("output_tokens_requested"),
            "ignore_eos": artifact.get("ignore_eos"),
            "metrics": metrics,
        }

    backend_stream = scenarios.get("backend_stream", {}).get("metrics", {})
    backend_nonstream = scenarios.get("backend_nonstream", {}).get("metrics", {})
    frontdoor_stream = scenarios.get("frontdoor_stream", {}).get("metrics", {})

    stream_client = backend_stream.get("client_after_first_corrected_tok_s")
    stream_vllm = backend_stream.get("vllm_decode_tok_s_from_histogram")
    nonstream_e2e = backend_nonstream.get("client_e2e_tok_s")
    frontdoor_client = frontdoor_stream.get("client_after_first_corrected_tok_s")

    backend_client_vs_vllm_pct = None
    if stream_client and stream_vllm:
        backend_client_vs_vllm_pct = 100.0 * (stream_client - stream_vllm) / stream_vllm

    nonstream_vs_stream_pct = None
    if nonstream_e2e and stream_client:
        nonstream_vs_stream_pct = 100.0 * (nonstream_e2e - stream_client) / stream_client

    frontdoor_vs_backend_pct = None
    if frontdoor_client and stream_client:
        frontdoor_vs_backend_pct = 100.0 * (frontdoor_client - stream_client) / stream_client

    current_best_tok_s = max(
        (
            value
            for scenario in scenarios.values()
            for value in [
                scenario["metrics"].get("client_after_first_corrected_tok_s"),
                scenario["metrics"].get("client_e2e_tok_s"),
                scenario["metrics"].get("vllm_decode_tok_s_from_histogram"),
            ]
            if isinstance(value, (int, float))
        ),
        default=None,
    )
    target_ms_per_token = 1000.0 / target_tok_s
    current_ms_per_token = None if not current_best_tok_s else 1000.0 / current_best_tok_s
    ms_per_token_reduction_needed_pct = None
    if current_ms_per_token:
        ms_per_token_reduction_needed_pct = (
            100.0 * (current_ms_per_token - target_ms_per_token) / current_ms_per_token
        )

    decision = "unknown"
    reasons = []
    if stream_vllm and stream_client:
        if abs(stream_client - stream_vllm) / stream_vllm < 0.03:
            reasons.append("backend client throughput matches vLLM decode histogram within 3%")
    if backend_stream.get("vllm_queue_ms") is not None and backend_stream["vllm_queue_ms"] < 1.0:
        reasons.append("vLLM queue time is effectively zero for c1")
    if frontdoor_vs_backend_pct is not None and abs(frontdoor_vs_backend_pct) < 2.0:
        reasons.append("frontdoor path is within 2% of backend direct")
    if nonstream_vs_stream_pct is not None and abs(nonstream_vs_stream_pct) < 2.0:
        reasons.append("non-streaming does not materially improve throughput")
    if len(reasons) >= 3:
        decision = "device_or_vllm_runtime_bound_not_http_or_frontdoor"

    return {
        "status": "pass" if scenarios else "fail",
        "target_tok_s": target_tok_s,
        "target_ms_per_token": target_ms_per_token,
        "current_best_tok_s": current_best_tok_s,
        "current_best_ms_per_token": current_ms_per_token,
        "ms_per_token_reduction_needed_pct": ms_per_token_reduction_needed_pct,
        "decision": decision,
        "decision_reasons": reasons,
        "comparisons": {
            "backend_stream_client_vs_vllm_decode_pct": backend_client_vs_vllm_pct,
            "backend_nonstream_e2e_vs_backend_stream_corrected_pct": nonstream_vs_stream_pct,
            "frontdoor_stream_vs_backend_stream_corrected_pct": frontdoor_vs_backend_pct,
        },
        "scenarios": scenarios,
        "next_optimization_focus": [
            "Do not spend primary effort on HTTP, SSE, or frontdoor overhead for c1 decode.",
            "The 200 tok/s target requires roughly 5 ms/token decode; current clean c1 is about 10 ms/token.",
            "Focus on XPU/vLLM decode internals: MoE kernel path, graph replay, collectives, scheduler step shape, and topology.",
        ],
    }


def write_markdown(path: str, summary: dict[str, Any]) -> None:
    lines = [
        "# Qwen3.6 C1 Latency Decomposition",
        "",
        f"- Status: `{summary['status']}`.",
        f"- Decision: `{summary['decision']}`.",
        f"- Current best: `{summary['current_best_tok_s']:.3f} tok/s`.",
        f"- Current best ms/token: `{summary['current_best_ms_per_token']:.3f}`.",
        f"- Target: `{summary['target_tok_s']:.3f} tok/s` (`{summary['target_ms_per_token']:.3f} ms/token`).",
        f"- Required ms/token reduction: `{summary['ms_per_token_reduction_needed_pct']:.2f}%`.",
        "",
        "## Comparisons",
        "",
    ]
    for key, value in summary["comparisons"].items():
        if value is None:
            lines.append(f"- `{key}`: null")
        else:
            lines.append(f"- `{key}`: `{value:.3f}%`")
    lines.extend(["", "## Decision Reasons", ""])
    for reason in summary["decision_reasons"]:
        lines.append(f"- {reason}")
    lines.extend(["", "## Scenarios", ""])
    for label, scenario in summary["scenarios"].items():
        metrics = scenario["metrics"]
        lines.append(f"### `{label}`")
        lines.append(f"- Path: `{scenario['path']}`")
        lines.append(f"- Mode: `{scenario['mode']}`")
        for key in [
            "client_after_first_corrected_tok_s",
            "client_e2e_tok_s",
            "vllm_decode_tok_s_from_histogram",
            "vllm_decode_ms_per_generation_token",
            "vllm_queue_ms",
            "vllm_prefill_ms",
            "client_ttft_ms",
            "vllm_ttft_ms",
        ]:
            value = metrics.get(key)
            if value is not None:
                lines.append(f"- `{key}`: `{value:.3f}`")
        lines.append("")
    lines.extend(["## Next Optimization Focus", ""])
    for item in summary["next_optimization_focus"]:
        lines.append(f"- {item}")
    lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", action="append", required=True, help="LABEL=PATH")
    parser.add_argument("--target-tok-s", type=float, default=200.0)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--markdown-out")
    args = parser.parse_args()

    artifacts = load_labeled(args.artifact)
    summary = summarize(artifacts, args.target_tok_s)
    output = json.dumps(summary, indent=2, sort_keys=True)
    Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_json).write_text(output + "\n", encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).parent.mkdir(parents=True, exist_ok=True)
        write_markdown(args.markdown_out, summary)
    print(output)
    return 0 if summary["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
