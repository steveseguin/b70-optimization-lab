#!/usr/bin/env python3
"""Summarize Qwen27 proposed-draft vs verifier-output trace rows.

This consumes the opt-in COW worker JSONL emitted by
``VLLM_XPU_DRAFT_ORACLE_TRACE=1`` plus ``VLLM_XPU_COW_WORKER_TRACE_FILE``.

The result is diagnostic only.  It answers whether the target-owned bonus /
replacement token appears later in the just-proposed draft row often enough to
justify a graph-safe branch/tail mechanism.  It does not prove that such tokens
can be committed, because after a replacement token the remaining draft tail was
conditioned on a different token history and GDN/DeltaNet state must be replayed
exactly before any valid speed claim.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict, deque
from pathlib import Path
from statistics import mean
from typing import Any


def _as_int_list(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    out: list[int] = []
    for item in value:
        try:
            out.append(int(item))
        except Exception:
            continue
    return out


def load_pairs(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pending: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
    pairs: list[dict[str, Any]] = []
    counters = Counter()

    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{line_no}: invalid JSON: {exc}") from exc

            stage = rec.get("stage")
            rows = (rec.get("extra") or {}).get("rows") or []

            if stage == "draft_oracle_proposed_tokens":
                for row in rows:
                    req_id = str(row.get("req_id"))
                    draft_ids = _as_int_list(row.get("draft_token_ids"))
                    if not req_id or not draft_ids:
                        continue
                    pending[req_id].append({
                        "draft_token_ids": draft_ids,
                        "sampled_token_ids": _as_int_list(
                            row.get("sampled_token_ids")),
                        "proposal_num_tokens_no_spec": row.get(
                            "num_tokens_no_spec"),
                        "proposal_num_computed_tokens_cpu": row.get(
                            "num_computed_tokens_cpu"),
                    })
                    counters["proposals"] += 1
                continue

            if stage != "mamba_state_update_begin":
                continue

            for row in rows:
                req_id = str(row.get("req_id"))
                scheduled_len = len(_as_int_list(row.get("scheduled_spec_ids")))
                if not req_id or scheduled_len <= 0:
                    continue
                counters["scheduled_verify_rows"] += 1
                if not pending.get(req_id):
                    counters["verify_rows_without_prior_proposal"] += 1
                    continue
                proposal = pending[req_id].popleft()
                output_ids = _as_int_list(row.get("output_token_ids"))
                raw_visible = int(row.get("raw_accepted_count", len(output_ids)) or 0)
                draft_ids = proposal["draft_token_ids"]
                k = min(len(draft_ids), scheduled_len)
                # Normal MTP verifier rows emit accepted draft prefix plus one
                # target-owned bonus/replacement token.
                accepted = max(0, min(k, raw_visible - 1))
                bonus = output_ids[accepted] if len(output_ids) > accepted else None
                prefix_match = output_ids[:accepted] == draft_ids[:accepted]
                first_rejected = draft_ids[accepted] if accepted < k else None
                bonus_tail_positions: list[int] = []
                if bonus is not None and accepted < k:
                    bonus_tail_positions = [
                        pos for pos in range(accepted, k)
                        if draft_ids[pos] == bonus
                    ]

                pairs.append({
                    "req_id": req_id,
                    "k": k,
                    "raw_visible": raw_visible,
                    "accepted_drafts": accepted,
                    "full_accept": accepted >= k,
                    "partial_reject": accepted < k,
                    "prefix_match": prefix_match,
                    "bonus_token": bonus,
                    "first_rejected_draft": first_rejected,
                    "bonus_in_unaccepted_draft_tail": bool(
                        bonus_tail_positions),
                    "bonus_tail_positions": bonus_tail_positions,
                    "draft_token_ids": draft_ids[:k],
                    "output_token_ids": output_ids,
                    **proposal,
                })

    remaining = sum(len(q) for q in pending.values())
    counters["unpaired_proposals_remaining"] = remaining
    return pairs, dict(counters)


def summarize(pairs: list[dict[str, Any]], counters: dict[str, Any]) -> dict[str, Any]:
    hist_accept = Counter(int(p["accepted_drafts"]) for p in pairs)
    hist_visible = Counter(int(p["raw_visible"]) for p in pairs)
    partial = [p for p in pairs if p["partial_reject"]]
    full = [p for p in pairs if p["full_accept"]]
    tail_hits = [p for p in partial if p["bonus_in_unaccepted_draft_tail"]]
    prefix_bad = [p for p in pairs if not p["prefix_match"]]
    current_visible = [int(p["raw_visible"]) for p in pairs]
    accepted = [int(p["accepted_drafts"]) for p in pairs]
    k_values = [int(p["k"]) for p in pairs]
    max_k = max(k_values) if k_values else 0
    mean_visible = mean(current_visible) if current_visible else None
    magic_all_full_visible = (max_k + 1) if max_k else None
    magic_same_cost_multiplier = (
        magic_all_full_visible / mean_visible
        if mean_visible and magic_all_full_visible else None
    )

    return {
        "classification": "qwen27_draft_oracle_trace_summary",
        "diagnostic_only": True,
        "notes": (
            "Bonus-in-tail is only an upper-bound signal. It is not a valid "
            "throughput claim and is not sufficient for correctness without "
            "graph-safe GDN/DeltaNet replay/branch verification."
        ),
        "counts": counters,
        "paired_rows": len(pairs),
        "partial_reject_rows": len(partial),
        "full_accept_rows": len(full),
        "partial_reject_rate": len(partial) / len(pairs) if pairs else None,
        "full_accept_rate": len(full) / len(pairs) if pairs else None,
        "mean_raw_visible_tokens": mean_visible,
        "mean_accepted_drafts": mean(accepted) if accepted else None,
        "max_k": max_k,
        "magic_all_full_visible_tokens": magic_all_full_visible,
        "magic_all_full_same_cost_multiplier": magic_same_cost_multiplier,
        "prefix_mismatch_rows": len(prefix_bad),
        "bonus_in_unaccepted_tail_rows": len(tail_hits),
        "bonus_in_unaccepted_tail_rate_over_partial": (
            len(tail_hits) / len(partial) if partial else None
        ),
        "bonus_in_unaccepted_tail_rate_over_all": (
            len(tail_hits) / len(pairs) if pairs else None
        ),
        "hist_accepted_drafts": dict(sorted(hist_accept.items())),
        "hist_raw_visible_tokens": dict(sorted(hist_visible.items())),
        "examples_bonus_tail_hits": tail_hits[:10],
        "examples_prefix_mismatch": prefix_bad[:10],
    }


def write_md(summary: dict[str, Any], out: Path, trace: Path) -> None:
    def fmt(v: Any) -> str:
        if isinstance(v, float):
            return f"{v:.6f}"
        return str(v)

    metric_keys = [
        "paired_rows",
        "partial_reject_rows",
        "partial_reject_rate",
        "full_accept_rows",
        "full_accept_rate",
        "mean_raw_visible_tokens",
        "mean_accepted_drafts",
        "max_k",
        "magic_all_full_visible_tokens",
        "magic_all_full_same_cost_multiplier",
        "prefix_mismatch_rows",
        "bonus_in_unaccepted_tail_rows",
        "bonus_in_unaccepted_tail_rate_over_partial",
        "bonus_in_unaccepted_tail_rate_over_all",
    ]
    lines = [
        "# Qwen27 Draft Oracle Trace Summary",
        "",
        "Classification: diagnostic only, no headline throughput result.",
        "",
        f"Trace: `{trace}`",
        "",
        "This asks whether the target-owned bonus/replacement token appears "
        "later in the same proposed draft row. A hit is only an upper-bound "
        "branch/tail signal; it is not valid to commit without exact "
        "target verification and GDN/DeltaNet state replay.",
        "",
        "| metric | value |",
        "| --- | ---: |",
    ]
    for key in metric_keys:
        lines.append(f"| `{key}` | {fmt(summary.get(key))} |")
    lines.extend([
        "",
        "Histograms:",
        "",
        "```json",
        json.dumps({
            "hist_accepted_drafts": summary.get("hist_accepted_drafts"),
            "hist_raw_visible_tokens": summary.get("hist_raw_visible_tokens"),
        }, indent=2, sort_keys=True),
        "```",
        "",
        "Counters:",
        "",
        "```json",
        json.dumps(summary.get("counts"), indent=2, sort_keys=True),
        "```",
        "",
    ])
    out.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", required=True, type=Path)
    ap.add_argument("--out-json", required=True, type=Path)
    ap.add_argument("--out-md", required=True, type=Path)
    args = ap.parse_args()

    pairs, counters = load_pairs(args.trace)
    summary = summarize(pairs, counters)
    summary["trace"] = str(args.trace)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_md(summary, args.out_md, args.trace)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
