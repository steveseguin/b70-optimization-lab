#!/usr/bin/env python3
"""Estimate legal branch/regenerate headroom from Qwen27 draft top-k traces.

This is a diagnostic cost model, not a benchmark.  The raw top-k oracle can
show that the target token often appears somewhere in the draft distribution,
but Qwen27 MTP drafting is sequential: replacing an early draft token makes the
later already-generated draft rows invalid.  A real endpoint win therefore
needs a legal branch/regenerate design that recomputes dependent draft rows, or
an equivalent branch/tree drafter, before target verification.

The model below asks a narrower engineering question:

* When the current MTP3 sequence first rejects at position ``a``, how often is
  the target token available in the draft top-k at that first rejected position?
* If a future legal implementation can pick that branch and regenerate the
  suffix perfectly, what is the optimistic target-verified tokens/step ceiling?
* Given the current valid record throughput, how much extra step cost can that
  design afford before it misses practical throughput targets?

The "perfect suffix" projection is deliberately optimistic.  It is useful as a
go/no-go bound: if even this bound cannot afford the needed work, the branch
lane is not worth implementing; if it can, the next task is a real source
prototype that measures the actual suffix regeneration cost and acceptance.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_CUTOFFS = (1, 2, 4, 8, 16, 32, 64)
DEFAULT_TARGET_TOK_S = (80.0, 90.0, 100.0, 125.0, 150.0)


def parse_csv_numbers(raw: str, *, cast=float) -> list[Any]:
    return [cast(item.strip()) for item in raw.split(",") if item.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft-topk", required=True,
                        help="Path to draft-topk.jsonl.")
    parser.add_argument("--verify-trace", required=True,
                        help="Path to verifier trace JSONL.")
    parser.add_argument(
        "--baseline-tok-s",
        type=float,
        default=67.51904968102535,
        help=("Valid current-record median tok/s used to normalize step cost. "
              "Default is the 2026-07-06 Qwen27 record."),
    )
    parser.add_argument(
        "--rank-cutoffs",
        default=",".join(str(x) for x in DEFAULT_CUTOFFS),
        help="Comma-separated top-k cutoffs to evaluate.",
    )
    parser.add_argument(
        "--target-tok-s",
        default=",".join(str(x) for x in DEFAULT_TARGET_TOK_S),
        help="Comma-separated throughput targets for extra-cost budgets.",
    )
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        row["_line_no"] = line_no
        rows.append(row)
    return rows


def verify_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        for rec in row.get("records") or []:
            num_draft = int(rec.get("num_draft_tokens") or 0)
            if num_draft <= 0:
                continue
            draft_ids = [int(x) for x in rec.get("draft_token_ids") or []]
            target_ids = [
                int(x) for x in rec.get("target_argmax_token_ids") or []
            ]
            if draft_ids and all(x == 0 for x in draft_ids):
                continue
            if len(draft_ids) < num_draft or len(target_ids) < num_draft:
                continue
            out.append({
                "num_draft_tokens": num_draft,
                "draft_ids": draft_ids[:num_draft],
                "target_ids": target_ids[:num_draft],
                "prefix_accepted": int(rec.get("prefix_accepted") or 0),
                "full_accept": bool(rec.get("full_accept")),
            })
    return out


def accepted_len(draft_ids: list[int], target_ids: list[int]) -> int:
    accepted = 0
    for draft_id, target_id in zip(draft_ids, target_ids):
        if draft_id != target_id:
            break
        accepted += 1
    return accepted


def group_sampled_ids(group: list[dict[str, Any]]) -> tuple[int, ...]:
    sampled: list[int] = []
    for row in group:
        sampled_ids = row.get("sampled_token_ids") or []
        if not sampled_ids:
            break
        sampled.append(int(sampled_ids[0]))
    return tuple(sampled)


def align_groups_to_verifier(
    groups: list[list[dict[str, Any]]],
    records: list[dict[str, Any]],
    *,
    lookahead: int = 64,
) -> tuple[list[tuple[list[dict[str, Any]], dict[str, Any]]], dict[str, Any]]:
    aligned: list[tuple[list[dict[str, Any]], dict[str, Any]]] = []
    skipped_groups = 0
    exact_matches = 0
    fallback_matches = 0
    fallback_examples: list[dict[str, Any]] = []
    group_index = 0

    for rec_index, rec in enumerate(records):
        wanted = tuple(rec["draft_ids"])
        found_index = None
        search_end = min(len(groups), group_index + lookahead)
        for candidate_index in range(group_index, search_end):
            sampled = group_sampled_ids(groups[candidate_index])
            if sampled[:len(wanted)] == wanted:
                found_index = candidate_index
                break

        if found_index is None:
            if group_index >= len(groups):
                break
            found_index = group_index
            fallback_matches += 1
            if len(fallback_examples) < 5:
                fallback_examples.append({
                    "record_index": rec_index,
                    "group_index": group_index,
                    "wanted": list(wanted),
                    "sampled": list(group_sampled_ids(groups[group_index])),
                })
        else:
            exact_matches += 1
            skipped_groups += found_index - group_index

        aligned.append((groups[found_index], rec))
        group_index = found_index + 1

    skipped_groups += max(0, len(groups) - group_index)
    return aligned, {
        "exact_group_matches": exact_matches,
        "fallback_matches": fallback_matches,
        "skipped_draft_groups": skipped_groups,
        "unused_verify_records": max(0, len(records) - len(aligned)),
        "fallback_examples": fallback_examples,
    }


def rank_of_target(row: dict[str, Any], target_id: int) -> int | None:
    top_ids_rows = row.get("top_token_ids") or []
    if not top_ids_rows:
        return None
    top_ids = [int(x) for x in top_ids_rows[0]]
    try:
        return top_ids.index(target_id) + 1
    except ValueError:
        return None


def build_groups(draft_rows: list[dict[str, Any]], expected_len: int) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for row in draft_rows:
        pos = int(row.get("draft_pos") or 0)
        if pos == 0 and current:
            groups.append(current)
            current = []
        current.append(row)
        if len(current) == expected_len:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def pct(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * p
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def summarize_values(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {
            "count": 0,
            "p10": None,
            "median": None,
            "mean": None,
            "min": None,
            "max": None,
            "stdev": None,
        }
    return {
        "count": len(values),
        "p10": pct(values, 0.10),
        "median": statistics.median(values),
        "mean": statistics.fmean(values),
        "min": min(values),
        "max": max(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def make_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Qwen27 Branch/Regenerate Feasibility Model",
        "",
        "Classification: diagnostic cost model, not a benchmark and not a LocalMaxxing submission.",
        "",
        "## Inputs",
        "",
        f"- draft top-k trace: `{summary['inputs']['draft_topk']}`",
        f"- verifier trace: `{summary['inputs']['verify_trace']}`",
        f"- normalized baseline tok/s: `{summary['baseline']['tok_s']}`",
        f"- baseline target-verified tokens/step: `{summary['baseline']['target_tokens_per_step']}`",
        f"- inferred baseline step ms: `{summary['baseline']['step_ms']}`",
        "",
        "## Current Acceptance",
        "",
        f"- aligned steps: `{summary['trace']['aligned_steps']}`",
        f"- accepted-prefix histogram: `{summary['trace']['accepted_prefix_hist']}`",
        f"- full-accept rate: `{summary['trace']['full_accept_rate']}`",
        "",
        "## Optimistic Legal Envelope",
        "",
        "This assumes a future legal branch/regenerate implementation can choose the",
        "target token at the first rejected position when it is inside draft top-k,",
        "then regenerate the remaining suffix perfectly. It is an upper bound, not",
        "an endpoint result.",
        "",
        "| cutoff | first-reject in top-k | projected tokens/step | no-extra-cost tok/s |",
        "| ---: | ---: | ---: | ---: |",
    ]
    for row in summary["cutoff_results"]:
        lines.append(
            f"| {row['rank_cutoff']} | {row['first_reject_target_in_topk_rate']:.6f} "
            f"| {row['optimistic_target_tokens_per_step']:.6f} "
            f"| {row['projected_tok_s_if_no_extra_step_cost']:.3f} |"
        )
    lines.extend([
        "",
        "## Extra Step-Cost Budget",
        "",
        "Positive numbers are the total additional milliseconds a branch/regenerate",
        "implementation could add per verifier step and still hit the target.",
        "",
        "| cutoff | 80 tok/s | 90 tok/s | 100 tok/s | 125 tok/s | 150 tok/s |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for row in summary["cutoff_results"]:
        budgets = row["extra_step_ms_budget"]
        lines.append(
            f"| {row['rank_cutoff']} "
            f"| {budgets['80.0']:.3f} "
            f"| {budgets['90.0']:.3f} "
            f"| {budgets['100.0']:.3f} "
            f"| {budgets['125.0']:.3f} "
            f"| {budgets['150.0']:.3f} |"
        )
    lines.extend([
        "",
        "## Interpretation",
        "",
        *[f"- {item}" for item in summary["interpretation"]],
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    draft_topk = Path(args.draft_topk)
    verify_trace = Path(args.verify_trace)
    cutoffs = [int(x) for x in parse_csv_numbers(args.rank_cutoffs, cast=int)]
    targets = [float(x) for x in parse_csv_numbers(args.target_tok_s, cast=float)]

    draft_rows = load_jsonl(draft_topk)
    records = verify_records(load_jsonl(verify_trace))
    if not records:
        raise SystemExit("No verifier records found.")
    num_draft_tokens = int(records[0]["num_draft_tokens"])
    groups = build_groups(draft_rows, num_draft_tokens)
    aligned, alignment = align_groups_to_verifier(groups, records)

    accepted_hist: Counter[int] = Counter()
    base_prefix_total = 0
    full_accepts = 0
    first_reject_attempts = 0
    first_reject_rank_hist: Counter[int | str] = Counter()
    per_step: list[dict[str, Any]] = []

    for group, rec in aligned:
        if len(group) < num_draft_tokens:
            continue
        draft_ids = rec["draft_ids"]
        target_ids = rec["target_ids"]
        accepted = accepted_len(draft_ids, target_ids)
        accepted_hist[accepted] += 1
        base_prefix_total += accepted
        if accepted >= num_draft_tokens:
            full_accepts += 1

        first_reject_rank = None
        if accepted < num_draft_tokens:
            first_reject_attempts += 1
            first_reject_rank = rank_of_target(group[accepted], target_ids[accepted])
            first_reject_rank_hist[
                "miss" if first_reject_rank is None else first_reject_rank
            ] += 1
        per_step.append({
            "accepted": accepted,
            "first_reject_rank": first_reject_rank,
        })

    steps = len(per_step)
    base_target_tokens_per_step = 1.0 + base_prefix_total / steps
    baseline_step_ms = (
        1000.0 * base_target_tokens_per_step / args.baseline_tok_s
    )

    cutoff_results: list[dict[str, Any]] = []
    for cutoff in cutoffs:
        optimistic_prefix_total = 0
        corrected_first_rejects = 0
        gains: list[float] = []
        for row in per_step:
            accepted = int(row["accepted"])
            rank = row["first_reject_rank"]
            optimistic_accepted = accepted
            if accepted < num_draft_tokens and rank is not None and rank <= cutoff:
                corrected_first_rejects += 1
                optimistic_accepted = num_draft_tokens
            optimistic_prefix_total += optimistic_accepted
            gains.append(float(optimistic_accepted - accepted))

        optimistic_tps = 1.0 + optimistic_prefix_total / steps
        projected_no_extra_cost = 1000.0 * optimistic_tps / baseline_step_ms
        budget = {
            f"{target:.1f}": (1000.0 * optimistic_tps / target) - baseline_step_ms
            for target in targets
        }
        cutoff_results.append({
            "rank_cutoff": cutoff,
            "corrected_first_rejects": corrected_first_rejects,
            "first_reject_target_in_topk_rate": (
                0.0 if first_reject_attempts == 0
                else corrected_first_rejects / first_reject_attempts
            ),
            "optimistic_target_tokens_per_step": optimistic_tps,
            "optimistic_incremental_tokens_per_step": (
                optimistic_tps - base_target_tokens_per_step
            ),
            "incremental_prefix_gain_stats": summarize_values(gains),
            "projected_tok_s_if_no_extra_step_cost": projected_no_extra_cost,
            "extra_step_ms_budget": budget,
        })

    required_tps = {
        f"{target:.1f}": target * baseline_step_ms / 1000.0
        for target in targets
    }
    best = cutoff_results[-1]
    interpretation = [
        ("The current sequential MTP3 trace has useful acceptance but not enough "
         "for 100 tok/s at the current step cost; 100 tok/s requires about "
         f"{required_tps['100.0']:.3f} target-verified tokens/step."),
        ("A one-token first-reject correction by itself does not increase output "
         "tokens per verifier step; a real win requires regenerating the suffix "
         "or an equivalent legal branch/tree drafter."),
        ("The rank-64 perfect-suffix envelope reaches "
         f"{best['optimistic_target_tokens_per_step']:.3f} tokens/step, which "
         f"would project to {best['projected_tok_s_if_no_extra_step_cost']:.1f} "
         "tok/s if it added no step cost."),
        ("For a 100 tok/s endpoint at rank-64, the branch/regenerate path can "
         f"spend at most {best['extra_step_ms_budget']['100.0']:.3f} ms extra "
         "per verifier step. The budgets for 125/150 tok/s are much tighter and "
         "likely require reducing verifier/LM-head cost too."),
        ("This uses the supplied draft top-k and verifier traces as the "
         "acceptance-shape evidence and normalizes step cost to the supplied "
         f"{args.baseline_tok_s:.6f} tok/s baseline. A source prototype still "
         "needs strict fresh validation."),
    ]

    summary = {
        "classification": "diagnostic_only_branch_regenerate_feasibility_model",
        "inputs": {
            "draft_topk": str(draft_topk),
            "verify_trace": str(verify_trace),
        },
        "baseline": {
            "tok_s": args.baseline_tok_s,
            "target_tokens_per_step": base_target_tokens_per_step,
            "step_ms": baseline_step_ms,
            "throughput_normalization_note": (
                "Step cost is normalized to the current valid Qwen27 record; "
                "acceptance shape comes from the existing top-k64 diagnostic trace."
            ),
        },
        "trace": {
            "draft_rows": len(draft_rows),
            "draft_groups": len(groups),
            "verify_records": len(records),
            "aligned_steps": steps,
            "alignment": alignment,
            "num_draft_tokens": num_draft_tokens,
            "accepted_prefix_hist": {
                str(k): v for k, v in sorted(accepted_hist.items())
            },
            "full_accept_rate": full_accepts / steps if steps else None,
            "first_reject_attempts": first_reject_attempts,
            "first_reject_rank_hist": {
                str(k): v for k, v in sorted(
                    first_reject_rank_hist.items(), key=lambda item: str(item[0])
                )
            },
        },
        "required_target_tokens_per_step_at_current_step_cost": required_tps,
        "cutoff_results": cutoff_results,
        "interpretation": interpretation,
    }

    text = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.out_json:
        Path(args.out_json).write_text(text)
    if args.out_md:
        Path(args.out_md).write_text(make_markdown(summary))
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
