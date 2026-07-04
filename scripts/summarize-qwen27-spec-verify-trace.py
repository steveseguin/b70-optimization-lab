#!/usr/bin/env python3
"""Summarize compact Qwen27 speculative verifier token traces.

Input is `VLLM_XPU_SPEC_DECODE_VERIFY_TRACE_FILE`, a default-off diagnostic
trace emitted by the XPU rejection sampler.  It records real draft token IDs,
target argmax token IDs, and verifier outputs without the heavy replay
microscope tensor/logit captures.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        row["_line_no"] = line_no
        rows.append(row)
    return rows


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


def stats(values: list[float]) -> dict[str, float | int | None]:
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


def summarize_trace(rows: list[dict[str, Any]]) -> dict[str, Any]:
    stage_hist = Counter(str(row.get("stage") or "") for row in rows)
    accepted_hist: Counter[int] = Counter()
    draft_hist: Counter[int] = Counter()
    per_pos_attempts: Counter[int] = Counter()
    per_pos_matches: Counter[int] = Counter()
    first_rejects: list[dict[str, Any]] = []
    steps = 0
    draft_tokens = 0
    prefix_accepted_tokens = 0
    independent_matches = 0
    full_accept_steps = 0
    output_tokens = 0
    stage_breakdown: dict[str, Counter[int]] = defaultdict(Counter)
    skipped_zero_draft_warmup_rows = 0

    for row in rows:
        stage = str(row.get("stage") or "")
        for record in row.get("records") or []:
            num_draft = int(record.get("num_draft_tokens") or 0)
            if num_draft <= 0:
                continue
            draft_ids = [int(tok) for tok in record.get("draft_token_ids") or []]
            # vLLM graph/profile warmup can execute the speculative sampler with
            # zero-filled dummy draft IDs before the endpoint is ready. Those
            # rows are not real requests and would otherwise look like total
            # rejection. Qwen real prompt rows should have non-zero draft IDs.
            if draft_ids and all(tok == 0 for tok in draft_ids):
                skipped_zero_draft_warmup_rows += 1
                continue
            accepted = int(record.get("prefix_accepted") or 0)
            outputs = record.get("output_token_ids") or []
            steps += 1
            draft_tokens += num_draft
            prefix_accepted_tokens += accepted
            output_tokens += len(outputs)
            accepted_hist[accepted] += 1
            draft_hist[num_draft] += 1
            stage_breakdown[stage][accepted] += 1
            if bool(record.get("full_accept")):
                full_accept_steps += 1

            target_ids = [
                int(tok) for tok in record.get("target_argmax_token_ids") or []
            ]
            for pos, (draft_id, target_id) in enumerate(zip(draft_ids, target_ids)):
                per_pos_attempts[pos] += 1
                if draft_id == target_id:
                    independent_matches += 1
                    per_pos_matches[pos] += 1
            if accepted < num_draft and len(first_rejects) < 16:
                first_rejects.append({
                    "line_no": row.get("_line_no"),
                    "stage": stage,
                    "position": accepted,
                    "draft_token_id": (
                        draft_ids[accepted] if accepted < len(draft_ids) else None
                    ),
                    "target_argmax_token_id": (
                        target_ids[accepted] if accepted < len(target_ids) else None
                    ),
                    "output_token_ids": outputs,
                })

    return {
        "trace_rows": len(rows),
        "stage_hist": dict(sorted(stage_hist.items())),
        "steps": steps,
        "draft_tokens": draft_tokens,
        "prefix_accepted_tokens": prefix_accepted_tokens,
        "independent_matching_tokens": independent_matches,
        "output_tokens": output_tokens,
        "prefix_acceptance_fraction": (
            None if draft_tokens <= 0 else prefix_accepted_tokens / draft_tokens
        ),
        "independent_match_fraction": (
            None if draft_tokens <= 0 else independent_matches / draft_tokens
        ),
        "mean_prefix_acceptance_length": (
            None if steps <= 0 else prefix_accepted_tokens / steps
        ),
        "mean_output_tokens_per_verifier_step": (
            None if steps <= 0 else output_tokens / steps
        ),
        "mean_target_verified_tokens_per_step": (
            None if steps <= 0 else 1.0 + prefix_accepted_tokens / steps
        ),
        "full_accept_steps": full_accept_steps,
        "full_accept_rate": None if steps <= 0 else full_accept_steps / steps,
        "accepted_hist": dict(sorted(accepted_hist.items())),
        "draft_hist": dict(sorted(draft_hist.items())),
        "per_position_match_rate": {
            str(pos): per_pos_matches[pos] / per_pos_attempts[pos]
            for pos in sorted(per_pos_attempts)
            if per_pos_attempts[pos]
        },
        "stage_prefix_accepted_hist": {
            stage: dict(sorted(hist.items()))
            for stage, hist in sorted(stage_breakdown.items())
        },
        "skipped_zero_draft_warmup_rows": skipped_zero_draft_warmup_rows,
        "first_reject_examples": first_rejects,
    }


def render_md(summary: dict[str, Any]) -> str:
    totals = summary["totals"]
    lines = [
        "# Qwen27 Spec Verify Trace Summary",
        "",
        f"- verify trace: `{summary['trace_path']}`",
        f"- result JSON: `{summary.get('result_path') or ''}`",
        "- classification: `diagnostic_only`; not a headline throughput claim",
        f"- trace rows: `{totals['trace_rows']}`",
        f"- skipped zero-draft warmup rows: `{totals['skipped_zero_draft_warmup_rows']}`",
        f"- verifier steps: `{totals['steps']}`",
        f"- draft tokens: `{totals['draft_tokens']}`",
        f"- prefix-accepted tokens: `{totals['prefix_accepted_tokens']}`",
        f"- prefix acceptance fraction: `{totals['prefix_acceptance_fraction']}`",
        f"- mean target-verified tokens per step: `{totals['mean_target_verified_tokens_per_step']}`",
        f"- mean output tokens per verifier step: `{totals['mean_output_tokens_per_verifier_step']}`",
        f"- full-accept rate: `{totals['full_accept_rate']}`",
        f"- accepted histogram: `{totals['accepted_hist']}`",
        f"- per-position target-top1 match: `{totals['per_position_match_rate']}`",
        "",
    ]
    if summary.get("result_summary"):
        speed = (summary["result_summary"] or {}).get("tok_s_1_100_after_ttft", {})
        ttft = (summary["result_summary"] or {}).get("ttft_ms", {})
        lines.extend([
            "## Paired Strict Result",
            "",
            f"- median tok/s 1-100 after TTFT: `{speed.get('median')}`",
            f"- p10 tok/s 1-100 after TTFT: `{speed.get('p10')}`",
            f"- mean tok/s 1-100 after TTFT: `{speed.get('mean')}`",
            f"- median TTFT ms: `{ttft.get('median')}`",
            f"- final gate: `{summary.get('realistic_final_gate')}`",
            "",
        ])
    lines.extend([
        "## First Reject Examples",
        "",
        "```json",
        json.dumps(totals["first_reject_examples"][:8], indent=2),
        "```",
        "",
        "## Interpretation",
        "",
        "- The trace is emitted inside the verifier sampler, so `draft_token_ids` are real worker-side proposals rather than scheduler placeholders.",
        "- Use this to decide whether drafter calibration can improve accepted tokens per verifier step.",
        "- Any speed claim still requires the strict cold realistic suite with `cached_tokens=0`.",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-jsonl", type=Path, required=True)
    parser.add_argument("--result-json", type=Path)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-md", type=Path)
    args = parser.parse_args()

    rows = load_jsonl(args.trace_jsonl)
    result = load_json(args.result_json) if args.result_json else None
    prompt_speeds = [
        float(row["tok_s_1_100_after_ttft"])
        for row in (result or {}).get("rows", [])
        if isinstance(row.get("tok_s_1_100_after_ttft"), (int, float))
    ]
    summary = {
        "trace_path": str(args.trace_jsonl),
        "result_path": str(args.result_json) if args.result_json else None,
        "classification": "diagnostic_only",
        "totals": summarize_trace(rows),
        "speed_stats": stats(prompt_speeds),
        "realistic_final_gate": (result or {}).get("realistic_final_gate"),
        "result_summary": (result or {}).get("summary"),
    }
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(summary, indent=2) + "\n")
    if args.out_md:
        args.out_md.parent.mkdir(parents=True, exist_ok=True)
        args.out_md.write_text(render_md(summary))
    print(json.dumps({
        "out_json": str(args.out_json),
        "out_md": str(args.out_md) if args.out_md else None,
        "steps": summary["totals"]["steps"],
        "prefix_acceptance_fraction": summary["totals"][
            "prefix_acceptance_fraction"
        ],
        "mean_target_verified_tokens_per_step": summary["totals"][
            "mean_target_verified_tokens_per_step"
        ],
        "speed_median": summary["speed_stats"]["median"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
