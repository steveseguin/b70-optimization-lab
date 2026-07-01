#!/usr/bin/env python3
"""Convert Qwen3.6 c1 endpoint metrics into a 200 tok/s latency budget."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any


def pick_summary_value(summary: dict[str, Any], key: str, field: str = "median") -> float | None:
    value = summary.get(key)
    if isinstance(value, dict) and value.get(field) is not None:
        return float(value[field])
    return None


def vals(records: list[dict[str, Any]], key: str) -> list[float]:
    out: list[float] = []
    for record in records:
        value = record.get(key)
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            out.append(float(value))
    return out


def stats(xs: list[float]) -> dict[str, float] | None:
    if not xs:
        return None
    return {
        "mean": statistics.mean(xs),
        "median": statistics.median(xs),
        "min": min(xs),
        "max": max(xs),
    }


def speedup_required_for_stage(total_ms: float, target_ms: float, stage_share: float) -> float | None:
    stage_ms = total_ms * stage_share
    required_saving = total_ms - target_ms
    if required_saving <= 0:
        return 1.0
    if stage_ms <= required_saving:
        return None
    return stage_ms / (stage_ms - required_saving)


def make_markdown(artifact: dict[str, Any]) -> str:
    b = artifact["budget"]
    lines = [
        "# Qwen3.6 C1 200 Tok/s Gap Budget",
        "",
        f"Input: `{artifact['input_metrics']}`",
        f"Target: `{b['target_tok_s']:.3f} tok/s` = `{b['target_ms_per_token']:.3f} ms/token`.",
        f"Current corrected decode: `{b['current_corrected_tok_s']:.3f} tok/s`.",
        f"Current decode histogram: `{b['current_decode_ms_per_token']:.3f} ms/token`.",
        f"Required saving: `{b['required_ms_saving_per_token']:.3f} ms/token` "
        f"(`{b['required_fractional_latency_reduction'] * 100:.1f}%` of current decode latency).",
        f"Required speedup over current corrected decode: `{b['required_speedup_factor']:.3f}x`.",
        "",
        "## Live Histogram",
        "",
        f"- Queue: `{b['queue_ms']:.4f} ms/request`.",
        f"- Prefill: `{b['prefill_ms']:.3f} ms/request` for the measured prompt.",
        f"- Decode: `{b['decode_ms_total']:.3f} ms/request`.",
        f"- Inter-token latency: `{b['inter_token_ms']:.3f} ms/token`.",
        f"- Iteration tokens per step: `{b['iteration_tokens_per_step']:.3f}`.",
        "",
        "## Stage Speedup Implication",
        "",
        "| Assumed optimized-stage share of decode | Required stage speedup |",
        "| ---: | ---: |",
    ]
    for row in artifact["stage_speedup_scenarios"]:
        speedup = row["required_stage_speedup"]
        speedup_text = "impossible" if speedup is None else f"{speedup:.2f}x"
        lines.append(f"| {row['stage_share'] * 100:.0f}% | {speedup_text} |")
    lines.extend([
        "",
        "Interpretation: a narrow micro-optimization cannot reach 200 tok/s alone. "
        "The winning path must remove about half the decode token latency, either "
        "through a large MoE/command-path improvement, target-verified multi-token "
        "acceptance, or a lower-latency topology that keeps the same model output.",
        "",
        "## Next Gates",
        "",
    ])
    for item in artifact["next_gates"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", required=True)
    parser.add_argument("--target-tok-s", type=float, default=200.0)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=True)
    args = parser.parse_args()

    metrics_path = Path(args.metrics)
    metrics = json.loads(metrics_path.read_text())
    summary = metrics.get("summary") or {}
    records = metrics.get("records") or []

    corrected_tok_s = pick_summary_value(
        summary, "tok_s_out_client_after_first_chunk_corrected"
    )
    after_first_tok_s = pick_summary_value(summary, "tok_s_out_client_after_first_chunk")
    e2e_tok_s = pick_summary_value(summary, "tok_s_out_client_e2e")
    decode_ms_per_token = pick_summary_value(
        summary, "decode_ms_per_generation_token_vllm_histogram"
    )
    if decode_ms_per_token is None:
        if corrected_tok_s is None:
            raise SystemExit("metrics artifact does not contain corrected tok/s or decode ms/token")
        decode_ms_per_token = 1000.0 / corrected_tok_s
    if corrected_tok_s is None:
        corrected_tok_s = 1000.0 / decode_ms_per_token

    target_ms = 1000.0 / args.target_tok_s
    required_saving = decode_ms_per_token - target_ms
    required_fraction = max(0.0, required_saving / decode_ms_per_token)
    required_speedup = args.target_tok_s / corrected_tok_s

    stage_rows = []
    for share in [0.25, 0.33, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]:
        stage_rows.append({
            "stage_share": share,
            "stage_ms_per_token": decode_ms_per_token * share,
            "required_stage_speedup": speedup_required_for_stage(
                decode_ms_per_token, target_ms, share
            ),
        })

    budget = {
        "target_tok_s": args.target_tok_s,
        "target_ms_per_token": target_ms,
        "current_corrected_tok_s": corrected_tok_s,
        "current_after_first_tok_s": after_first_tok_s,
        "current_e2e_tok_s": e2e_tok_s,
        "current_decode_ms_per_token": decode_ms_per_token,
        "required_ms_saving_per_token": required_saving,
        "required_fractional_latency_reduction": required_fraction,
        "required_speedup_factor": required_speedup,
        "queue_ms": pick_summary_value(summary, "queue_ms_vllm_histogram") or 0.0,
        "prefill_ms": pick_summary_value(summary, "prefill_ms_vllm_histogram") or 0.0,
        "decode_ms_total": pick_summary_value(summary, "decode_ms_vllm_histogram") or 0.0,
        "inter_token_ms": pick_summary_value(summary, "inter_token_ms_vllm_histogram")
        or decode_ms_per_token,
        "iteration_tokens_per_step": pick_summary_value(
            summary, "iteration_tokens_per_step_vllm_histogram"
        )
        or 0.0,
        "ttft_ms": pick_summary_value(summary, "ttft_ms_vllm_metrics") or 0.0,
        "record_count": len(records),
        "record_corrected_tok_s": stats(
            vals(records, "tok_s_out_client_after_first_chunk_corrected")
        ),
        "record_decode_ms_per_token": stats(
            vals(records, "decode_ms_per_generation_token_vllm_histogram")
        ),
    }

    artifact = {
        "input_metrics": str(metrics_path),
        "model": metrics.get("model"),
        "server_model_root": (metrics.get("server_model_record") or {}).get("root"),
        "prompt_tokens": metrics.get("prompt_tokens_actual"),
        "output_tokens": metrics.get("output_tokens_requested"),
        "mode": metrics.get("mode"),
        "ignore_eos": metrics.get("ignore_eos"),
        "budget": budget,
        "stage_speedup_scenarios": stage_rows,
        "next_gates": [
            "Do not spend time on queue/frontdoor fixes first; measured queue time is effectively zero for c1.",
            "Use the sidecar/oneDNN path only if it can attack multi-millisecond decode latency, not just a microsecond GEMM slice.",
            "Add device-side token-step timing before committing to a custom kernel so attention, GDN, MoE, collectives, sampler, and scheduler costs are ranked.",
            "Treat target-verified MTP/DFlash/ngram transactions as a separate 2x-class path because they can reduce effective emitted-token latency without changing accepted output.",
            "Revisit TP2/single-lane topology only with exact current-model canaries, because TP4 may be paying collective/control overhead for c1.",
        ],
    }

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(artifact, indent=2) + "\n")
    out_md.write_text(make_markdown(artifact))
    print(json.dumps(budget, indent=2))
    print(f"wrote={out_json}")
    print(f"wrote={out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
