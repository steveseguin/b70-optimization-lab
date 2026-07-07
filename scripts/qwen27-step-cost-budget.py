#!/usr/bin/env python3
"""Compute Qwen27 strict-decode step-cost budgets.

This is a CPU-only planning artifact, not a benchmark.  It answers whether a
proposed Qwen3.6 27B INT4 optimization has enough theoretical headroom before
we spend GPU time on implementation.

The current best Qwen27 recipe is target-verified MTP3.  Its throughput is set
by two variables:

    tok/s = target_verified_tokens_per_step * 1000 / verifier_step_ms

Therefore a candidate can only reach a target throughput by reducing verifier
step cost, increasing target-verified tokens per step, or both.  The script
prints the required savings and accepted-depth requirements for common targets.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_TOK_S = 68.23626314761921
DEFAULT_TOKENS_PER_STEP = 2.746954076850984
DEFAULT_TARGETS = (80.0, 90.0, 100.0, 125.0, 150.0)


def parse_csv_floats(raw: str) -> list[float]:
    return [float(item.strip()) for item in raw.split(",") if item.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-tok-s", type=float, default=DEFAULT_TOK_S)
    parser.add_argument(
        "--tokens-per-step",
        type=float,
        default=DEFAULT_TOKENS_PER_STEP,
        help="Current target-verified visible tokens emitted per verifier step.",
    )
    parser.add_argument(
        "--targets",
        default=",".join(str(x) for x in DEFAULT_TARGETS),
        help="Comma-separated target throughputs to budget.",
    )
    parser.add_argument(
        "--max-mtp3-tokens-per-step",
        type=float,
        default=4.0,
        help="Hard target-verified token/step ceiling for MTP3: 3 draft + 1 bonus.",
    )
    parser.add_argument(
        "--branch-envelope-tokens-per-step",
        type=float,
        default=3.9681349578256793,
        help=(
            "Current rank-64 optimistic legal MTP3 branch/regenerate envelope. "
            "Set to 0 to omit."
        ),
    )
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    return parser.parse_args()


def row_for_target(
    *,
    target_tok_s: float,
    current_step_ms: float,
    tokens_per_step: float,
    max_mtp3_tokens_per_step: float,
    branch_envelope_tokens_per_step: float,
) -> dict[str, Any]:
    required_step_ms_at_current_depth = tokens_per_step * 1000.0 / target_tok_s
    required_step_saving_ms = current_step_ms - required_step_ms_at_current_depth
    required_step_saving_pct = (
        required_step_saving_ms / current_step_ms * 100.0
        if current_step_ms > 0
        else None
    )
    required_tokens_at_current_step = target_tok_s * current_step_ms / 1000.0
    max_mtp3_tok_s_at_current_step = (
        max_mtp3_tokens_per_step * 1000.0 / current_step_ms
    )
    branch_envelope_tok_s = None
    branch_extra_step_budget_ms = None
    if branch_envelope_tokens_per_step > 0:
        branch_envelope_tok_s = (
            branch_envelope_tokens_per_step * 1000.0 / current_step_ms
        )
        branch_extra_step_budget_ms = (
            branch_envelope_tokens_per_step * 1000.0 / target_tok_s
            - current_step_ms
        )
    return {
        "target_tok_s": target_tok_s,
        "required_step_ms_at_current_depth": required_step_ms_at_current_depth,
        "required_step_saving_ms": required_step_saving_ms,
        "required_step_saving_pct": required_step_saving_pct,
        "required_tokens_per_step_at_current_step_ms": (
            required_tokens_at_current_step
        ),
        "current_mtp3_hard_ceiling_tok_s_at_current_step_ms": (
            max_mtp3_tok_s_at_current_step
        ),
        "current_mtp3_hard_ceiling_can_reach": (
            max_mtp3_tok_s_at_current_step >= target_tok_s
        ),
        "branch_envelope_tok_s_at_current_step_ms": branch_envelope_tok_s,
        "branch_envelope_extra_step_budget_ms": branch_extra_step_budget_ms,
        "branch_envelope_can_reach_without_step_reduction": (
            bool(branch_envelope_tok_s is not None
                 and branch_envelope_tok_s >= target_tok_s)
        ),
    }


def make_summary(args: argparse.Namespace) -> dict[str, Any]:
    targets = parse_csv_floats(args.targets)
    current_step_ms = args.tokens_per_step * 1000.0 / args.baseline_tok_s
    rows = [
        row_for_target(
            target_tok_s=target,
            current_step_ms=current_step_ms,
            tokens_per_step=args.tokens_per_step,
            max_mtp3_tokens_per_step=args.max_mtp3_tokens_per_step,
            branch_envelope_tokens_per_step=args.branch_envelope_tokens_per_step,
        )
        for target in targets
    ]
    return {
        "classification": "diagnostic_only_qwen27_step_cost_budget",
        "baseline": {
            "tok_s": args.baseline_tok_s,
            "target_verified_tokens_per_step": args.tokens_per_step,
            "inferred_verifier_step_ms": current_step_ms,
            "max_mtp3_tokens_per_step": args.max_mtp3_tokens_per_step,
            "branch_envelope_tokens_per_step": (
                args.branch_envelope_tokens_per_step
            ),
        },
        "target_rows": rows,
        "interpretation": [
            (
                "At fixed accepted depth, reaching a target tok/s requires "
                "reducing verifier step ms by the listed required_step_saving_ms."
            ),
            (
                "At fixed step cost, reaching a target tok/s requires the listed "
                "required_tokens_per_step_at_current_step_ms."
            ),
            (
                "MTP3 has a hard ceiling of 4 target-verified tokens/step; "
                "anything above that needs deeper speculation or a different "
                "verified-draft mechanism."
            ),
            (
                "Negative branch_envelope_extra_step_budget_ms means even the "
                "optimistic rank-64 MTP3 branch/regenerate model misses that "
                "target before implementation overhead."
            ),
        ],
    }


def make_markdown(summary: dict[str, Any]) -> str:
    base = summary["baseline"]
    lines = [
        "# Qwen27 Step-Cost Budget",
        "",
        "Classification: diagnostic planning artifact, not a benchmark and not a LocalMaxxing submission.",
        "",
        "## Baseline",
        "",
        f"- strict fresh headline: `{base['tok_s']}` tok/s",
        f"- target-verified tokens/step: `{base['target_verified_tokens_per_step']}`",
        f"- inferred verifier step cost: `{base['inferred_verifier_step_ms']}` ms",
        f"- MTP3 hard ceiling: `{base['max_mtp3_tokens_per_step']}` target-verified tokens/step",
        f"- current rank-64 branch envelope: `{base['branch_envelope_tokens_per_step']}` tokens/step",
        "",
        "## Throughput Targets",
        "",
        "| target tok/s | step ms needed at current depth | step ms to save | save % | tokens/step needed at current step | MTP3 hard ceiling reaches? | branch envelope tok/s | branch extra step budget |",
        "|---:|---:|---:|---:|---:|:---:|---:|---:|",
    ]
    for row in summary["target_rows"]:
        branch_tok_s = row["branch_envelope_tok_s_at_current_step_ms"]
        branch_budget = row["branch_envelope_extra_step_budget_ms"]
        branch_tok_s_text = (
            f"{branch_tok_s:.3f}" if branch_tok_s is not None else "n/a"
        )
        branch_budget_text = (
            f"{branch_budget:.3f}" if branch_budget is not None else "n/a"
        )
        lines.append(
            "| "
            f"{row['target_tok_s']:.1f} | "
            f"{row['required_step_ms_at_current_depth']:.3f} | "
            f"{row['required_step_saving_ms']:.3f} | "
            f"{row['required_step_saving_pct']:.2f}% | "
            f"{row['required_tokens_per_step_at_current_step_ms']:.3f} | "
            f"{'yes' if row['current_mtp3_hard_ceiling_can_reach'] else 'no'} | "
            f"{branch_tok_s_text} | "
            f"{branch_budget_text} |"
        )
    lines.extend([
        "",
        "## Reading This",
        "",
        "- A verifier-step-cost patch that saves less than the listed `step ms to save` cannot hit that target unless accepted depth also improves.",
        "- Current MTP3 cannot reach `100 tok/s` at the measured step cost; even the optimistic rank-64 branch envelope tops out below `100 tok/s` before overhead.",
        "- `125+ tok/s` requires deeper verified speculation or a large target-body step-cost reduction plus better accepted depth.",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    summary = make_summary(args)
    if args.out_json:
        Path(args.out_json).write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.out_md:
        Path(args.out_md).write_text(make_markdown(summary), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
