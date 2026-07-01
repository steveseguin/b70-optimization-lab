#!/usr/bin/env python3
"""Estimate verifier-only speculative decode upper bounds from bucket timings.

The inputs are synchronized XPU timing summaries from
``summarize-xpu-decode-timing-log.py``. These are not endpoint speed results.
They answer a narrower question: if a proposer supplied correct draft tokens,
how much sublinear verifier work is available at each decode bucket size?
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


DEFAULT_INPUTS = [
    "data/qwen36-quark-int8-tp4-decode-bucket-timing-summary-20260611.json",
    "data/qwen36-quark-int8-tp4-ngram2-bucket-timing-natural-summary-20260611.json",
    "data/qwen36-quark-int8-tp4-ngram2-bucket-timing-repetitive-summary-20260611.json",
    "data/qwen36-quark-int8-tp4-ngram5-bucket-timing-repetitive-summary-20260611.json",
    "data/qwen36-quark-int8-tp4-ngram7-bucket-timing-repetitive-summary-20260611.json",
]

DEFAULT_ACCEPT_FRACTIONS = [0.0, 0.25, 0.5, 0.75, 0.9, 1.0]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def collect_observations(paths: list[Path]) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for path in paths:
        data = load_json(path)
        for summary in data.get("step_summary_by_bucket", []):
            group = summary.get("group", {})
            if not group.get("is_pure_decode"):
                continue
            bucket = group.get("decode_bucket")
            if not bucket:
                continue
            mean_model_ms = as_float(summary.get("mean_model_forward_ms"))
            mean_visible_ms = as_float(summary.get("mean_visible_timed_ms"))
            if mean_model_ms is None or mean_visible_ms is None:
                continue
            observations.append(
                {
                    "source": str(path),
                    "bucket": int(bucket),
                    "max_scheduled_spec_tokens": int(
                        group.get("max_scheduled_spec_tokens") or 0
                    ),
                    "step_count": int(summary.get("step_count") or 0),
                    "mean_model_forward_ms": mean_model_ms,
                    "mean_visible_timed_ms": mean_visible_ms,
                    "median_model_forward_ms": as_float(
                        summary.get("median_model_forward_ms")
                    ),
                    "median_visible_timed_ms": as_float(
                        summary.get("median_visible_timed_ms")
                    ),
                    "p90_model_forward_ms": as_float(summary.get("p90_model_forward_ms")),
                    "p90_visible_timed_ms": as_float(
                        summary.get("p90_visible_timed_ms")
                    ),
                    "scheduled_token_histogram_total": summary.get(
                        "scheduled_token_histogram_total", {}
                    ),
                    "scheduled_spec_histogram_total": summary.get(
                        "scheduled_spec_histogram_total", {}
                    ),
                }
            )
    observations.sort(
        key=lambda row: (
            row["bucket"],
            row["mean_model_forward_ms"],
            row["mean_visible_timed_ms"],
            row["source"],
        )
    )
    return observations


def best_by_bucket(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[int, dict[str, Any]] = {}
    for row in observations:
        bucket = int(row["bucket"])
        current = best.get(bucket)
        if current is None or row["mean_model_forward_ms"] < current[
            "mean_model_forward_ms"
        ]:
            best[bucket] = dict(row)
    return [best[bucket] for bucket in sorted(best)]


def accept_fraction_for_target(
    *,
    target_tok_s: float,
    ms_per_step: float,
    bucket: int,
) -> float | None:
    if bucket <= 1:
        return None
    tokens_needed = target_tok_s * ms_per_step / 1000.0
    return max(0.0, min(1.0, (tokens_needed - 1.0) / float(bucket - 1)))


def overhead_budget_ms_for_target(
    *,
    target_tok_s: float,
    expected_tokens_per_step: float,
    base_step_ms: float,
) -> float:
    """Return additional ms/step available before dropping below target tok/s."""
    max_step_ms = 1000.0 * expected_tokens_per_step / target_tok_s
    return max_step_ms - base_step_ms


def endpoint_scaled_overhead_budget_ms_for_target(
    *,
    target_tok_s: float,
    baseline_endpoint_tok_s: float,
    baseline_bucket1_model_ms: float,
    expected_tokens_per_step: float,
    base_model_ms: float,
) -> float:
    """Overhead budget using endpoint-normalized model-forward timing.

    The endpoint-scaled estimate maps a synchronized model-forward bucket timing
    back to the accepted endpoint row. Solving the same expression for the
    maximum allowed step time gives an endpoint-normalized COW/scheduler budget.
    """
    max_model_ms = (
        baseline_endpoint_tok_s
        * expected_tokens_per_step
        * baseline_bucket1_model_ms
        / target_tok_s
    )
    return max_model_ms - base_model_ms


def parse_accept_fractions(value: str) -> list[float]:
    fractions: list[float] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        fraction = float(part)
        if fraction < 0.0 or fraction > 1.0:
            raise argparse.ArgumentTypeError(
                f"accept fraction must be between 0 and 1: {part}"
            )
        fractions.append(fraction)
    if not fractions:
        raise argparse.ArgumentTypeError("at least one accept fraction is required")
    return fractions


def add_estimates(
    rows: list[dict[str, Any]],
    *,
    baseline_endpoint_tok_s: float,
    baseline_bucket1_model_ms: float,
    target_tok_s: float,
    accept_fractions: list[float],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        row = dict(row)
        bucket = int(row["bucket"])
        model_ms = float(row["mean_model_forward_ms"])
        visible_ms = float(row["mean_visible_timed_ms"])
        row["perfect_accept_model_forward_tok_s"] = 1000.0 * bucket / model_ms
        row["perfect_accept_visible_timed_tok_s"] = 1000.0 * bucket / visible_ms
        row["perfect_accept_endpoint_scaled_tok_s"] = (
            baseline_endpoint_tok_s * bucket * baseline_bucket1_model_ms / model_ms
        )
        row["model_forward_accept_fraction_for_target"] = accept_fraction_for_target(
            target_tok_s=target_tok_s,
            ms_per_step=model_ms,
            bucket=bucket,
        )
        row["visible_timed_accept_fraction_for_target"] = accept_fraction_for_target(
            target_tok_s=target_tok_s,
            ms_per_step=visible_ms,
            bucket=bucket,
        )
        row["perfect_accept_model_forward_overhead_budget_ms"] = (
            overhead_budget_ms_for_target(
                target_tok_s=target_tok_s,
                expected_tokens_per_step=float(bucket),
                base_step_ms=model_ms,
            )
        )
        row["perfect_accept_visible_timed_overhead_budget_ms"] = (
            overhead_budget_ms_for_target(
                target_tok_s=target_tok_s,
                expected_tokens_per_step=float(bucket),
                base_step_ms=visible_ms,
            )
        )
        row["perfect_accept_endpoint_scaled_overhead_budget_ms"] = (
            endpoint_scaled_overhead_budget_ms_for_target(
                target_tok_s=target_tok_s,
                baseline_endpoint_tok_s=baseline_endpoint_tok_s,
                baseline_bucket1_model_ms=baseline_bucket1_model_ms,
                expected_tokens_per_step=float(bucket),
                base_model_ms=model_ms,
            )
        )

        rate_rows = []
        for draft_accept_fraction in accept_fractions:
            expected_tokens = 1.0 + draft_accept_fraction * max(0, bucket - 1)
            rate_rows.append(
                {
                    "draft_accept_fraction": draft_accept_fraction,
                    "expected_tokens_per_step": expected_tokens,
                    "model_forward_tok_s": 1000.0 * expected_tokens / model_ms,
                    "visible_timed_tok_s": 1000.0 * expected_tokens / visible_ms,
                    "endpoint_scaled_tok_s": (
                        baseline_endpoint_tok_s
                        * expected_tokens
                        * baseline_bucket1_model_ms
                        / model_ms
                    ),
                    "model_forward_overhead_budget_ms": overhead_budget_ms_for_target(
                        target_tok_s=target_tok_s,
                        expected_tokens_per_step=expected_tokens,
                        base_step_ms=model_ms,
                    ),
                    "visible_timed_overhead_budget_ms": overhead_budget_ms_for_target(
                        target_tok_s=target_tok_s,
                        expected_tokens_per_step=expected_tokens,
                        base_step_ms=visible_ms,
                    ),
                    "endpoint_scaled_overhead_budget_ms": (
                        endpoint_scaled_overhead_budget_ms_for_target(
                            target_tok_s=target_tok_s,
                            baseline_endpoint_tok_s=baseline_endpoint_tok_s,
                            baseline_bucket1_model_ms=baseline_bucket1_model_ms,
                            expected_tokens_per_step=expected_tokens,
                            base_model_ms=model_ms,
                        )
                    ),
                }
            )
        row["estimates_by_draft_accept_fraction"] = rate_rows
        out.append(row)
    return out


def fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def fmt_pct_fraction(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value) * 100.0:.1f}%"


def write_markdown(path: Path, output: dict[str, Any]) -> None:
    rows = output["best_by_bucket"]
    accept_fractions = output["accept_fractions"]
    lines = [
        "# Qwen3.6 Verifier Upper-Bound Estimate",
        "",
        "This is a timing-derived upper-bound analysis, not a promoted endpoint result.",
        "It assumes the current Quark INT8 model remains the final verifier and asks",
        "how much speed would be available if a proposer supplied correct drafts.",
        "",
        f"- Baseline endpoint steady-state tok/s: `{output['baseline_endpoint_tok_s']:.6f}`",
        f"- Baseline bucket-1 model-forward timing: `{output['baseline_bucket1_model_ms']:.6f} ms`",
        f"- Target: `{output['target_tok_s']:.1f} tok/s`",
        "",
        "| Bucket | Steps | Model ms | Visible ms | Perfect model tok/s | Perfect visible tok/s | Endpoint-scaled tok/s | Accept frac for 200 (model) | Source |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        source = Path(row["source"]).name
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["bucket"]),
                    str(row["step_count"]),
                    fmt(row["mean_model_forward_ms"], 3),
                    fmt(row["mean_visible_timed_ms"], 3),
                    fmt(row["perfect_accept_model_forward_tok_s"], 2),
                    fmt(row["perfect_accept_visible_timed_tok_s"], 2),
                    fmt(row["perfect_accept_endpoint_scaled_tok_s"], 2),
                    fmt_pct_fraction(row["model_forward_accept_fraction_for_target"]),
                    f"`{source}`",
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## COW / Scheduler Overhead Budget",
            "",
            "The values below are additional milliseconds per speculative verifier",
            "step that can be spent on copy-on-write request/KV setup, scheduler",
            "bookkeeping, scratch block allocation/free, and result commit before",
            f"falling below `{output['target_tok_s']:.1f} tok/s`.",
            "",
            "Positive budget means the bucket could still hit the target after that",
            "much extra overhead. Negative budget means the bucket already misses",
            "the target at that acceptance fraction.",
            "",
            "| Bucket | Accept frac | Expected tokens/step | Model budget ms | Visible budget ms | Endpoint-scaled budget ms |",
            "| ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rows:
        for estimate in row["estimates_by_draft_accept_fraction"]:
            fraction = float(estimate["draft_accept_fraction"])
            if fraction not in accept_fractions:
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(row["bucket"]),
                        fmt_pct_fraction(fraction),
                        fmt(estimate["expected_tokens_per_step"], 3),
                        fmt(estimate["model_forward_overhead_budget_ms"], 3),
                        fmt(estimate["visible_timed_overhead_budget_ms"], 3),
                        fmt(estimate["endpoint_scaled_overhead_budget_ms"], 3),
                    ]
                )
                + " |"
            )

    lines.extend(
        [
            "",
            "Interpretation:",
            "",
            "- Bucket 3 is already near the 200 tok/s line on synchronized model-forward timing and clears it on endpoint-scaled timing.",
            "- Buckets 6 and 8 have enough sublinear verifier scaling to clear 200 tok/s if draft correctness and scheduler state are fixed.",
            "- The rejected n-gram and hybrid MTP runs failed quality, so these numbers are only an upper bound for a future exact proposer.",
            "- If a true perfect-draft harness comes in materially below this estimate, pivot back to persistent MoE/layout work.",
            "- The COW patch should log actual scratch/fork overhead and compare it to the endpoint-scaled budget above.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        action="append",
        dest="inputs",
        default=None,
        help="Timing summary JSON. May be repeated. Defaults to current Qwen3.6 bucket artifacts.",
    )
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    parser.add_argument("--target-tok-s", type=float, default=200.0)
    parser.add_argument(
        "--accept-fractions",
        type=parse_accept_fractions,
        default=DEFAULT_ACCEPT_FRACTIONS,
        help=(
            "Comma-separated draft acceptance fractions for overhead-budget rows. "
            "Default: 0,0.25,0.5,0.75,0.9,1"
        ),
    )
    parser.add_argument(
        "--baseline-endpoint-tok-s",
        type=float,
        default=99.76969927367736,
        help="Accepted non-speculative endpoint steady-state tok/s used for endpoint-scaled estimates.",
    )
    args = parser.parse_args()

    paths = [Path(p) for p in (args.inputs or DEFAULT_INPUTS)]
    observations = collect_observations(paths)
    if not observations:
        raise SystemExit("no pure-decode bucket observations found")

    bucket1_rows = [row for row in observations if int(row["bucket"]) == 1]
    if not bucket1_rows:
        raise SystemExit("no bucket-1 baseline observation found")
    baseline_bucket1_model_ms = min(
        float(row["mean_model_forward_ms"]) for row in bucket1_rows
    )

    best = add_estimates(
        best_by_bucket(observations),
        baseline_endpoint_tok_s=args.baseline_endpoint_tok_s,
        baseline_bucket1_model_ms=baseline_bucket1_model_ms,
        target_tok_s=args.target_tok_s,
        accept_fractions=args.accept_fractions,
    )
    detailed = add_estimates(
        observations,
        baseline_endpoint_tok_s=args.baseline_endpoint_tok_s,
        baseline_bucket1_model_ms=baseline_bucket1_model_ms,
        target_tok_s=args.target_tok_s,
        accept_fractions=args.accept_fractions,
    )
    output = {
        "method_caveat": (
            "Uses synchronized internal timing summaries. It estimates verifier "
            "upper bounds under perfect draft acceptance; it is not a live "
            "endpoint throughput result and not a quality proof."
        ),
        "inputs": [str(path) for path in paths],
        "target_tok_s": args.target_tok_s,
        "accept_fractions": args.accept_fractions,
        "baseline_endpoint_tok_s": args.baseline_endpoint_tok_s,
        "baseline_bucket1_model_ms": baseline_bucket1_model_ms,
        "best_by_bucket": best,
        "observations": detailed,
        "notes": [
            "Endpoint-scaled estimates normalize bucket timing against the accepted non-speculative endpoint row.",
            "Visible-timed estimates are conservative because synchronization instrumentation slows serving.",
            "Draft accept fraction assumes expected emitted tokens = 1 + fraction * (bucket - 1).",
        ],
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    write_markdown(args.output_md, output)
    print(
        json.dumps(
            {
                "output_json": str(args.output_json),
                "output_md": str(args.output_md),
                "buckets": [row["bucket"] for row in best],
                "best_endpoint_scaled_tok_s": max(
                    row["perfect_accept_endpoint_scaled_tok_s"] for row in best
                ),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
