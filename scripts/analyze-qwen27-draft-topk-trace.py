#!/usr/bin/env python3
"""Join Qwen27 MTP draft top-k traces with verifier traces.

This is diagnostic-only. It estimates whether a draft-only calibration layer
has useful headroom by checking whether target verifier top IDs appear in the
draft model's top-k alternatives for each MTP position. The reported top-k
oracle is an independent per-position upper bound; Qwen27's current MTP
proposer is sequential, so changing an early draft token would require
regenerating later draft positions or using a correct branch/tree drafter.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft-topk", required=True)
    parser.add_argument("--verify-trace", required=True)
    parser.add_argument("--out", default="")
    return parser.parse_args()


def load_jsonl(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(Path(path).read_text().splitlines(), 1):
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
                "draft_ids": draft_ids[:num_draft],
                "target_ids": target_ids[:num_draft],
                "prefix_accepted": int(rec.get("prefix_accepted") or 0),
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
    """Align proposer top-k groups to verifier records.

    The draft trace can include extra proposer groups around request boundaries
    or warmup/profile paths that do not produce a verifier record. A single
    global offset therefore drifts. The sampled draft tuple is the stable join
    key: for a real verification step it must match the verifier's
    draft_token_ids exactly.
    """

    aligned: list[tuple[list[dict[str, Any]], dict[str, Any]]] = []
    skipped_groups = 0
    exact_matches = 0
    fallback_matches = 0
    fallback_examples: list[dict[str, Any]] = []
    group_index = 0

    for rec_index, rec in enumerate(records):
        wanted = tuple(rec["draft_ids"][:3])
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
    meta = {
        "exact_group_matches": exact_matches,
        "fallback_matches": fallback_matches,
        "skipped_draft_groups": skipped_groups,
        "unused_verify_records": max(0, len(records) - len(aligned)),
        "fallback_examples": fallback_examples,
    }
    return aligned, meta


def main() -> int:
    args = parse_args()
    draft_rows = load_jsonl(args.draft_topk)
    ver_rows = verify_records(load_jsonl(args.verify_trace))

    # Keep only the common MTP3 shape and group the draft trace into proposer
    # steps. Warmup/profile rows can make the streams unequal, so align on the
    # longest suffix with matching first-choice draft IDs.
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for row in draft_rows:
        pos = row.get("draft_pos")
        if pos == 0 and current:
            groups.append(current)
            current = []
        current.append(row)
        if len(current) == 3:
            groups.append(current)
            current = []
    if current:
        groups.append(current)

    aligned, alignment_meta = align_groups_to_verifier(groups, ver_rows)

    per_pos_attempts: Counter[int] = Counter()
    per_pos_match: Counter[int] = Counter()
    per_pos_in_topk: Counter[int] = Counter()
    per_pos_rank_hist: dict[int, Counter[int | str]] = {
        0: Counter(),
        1: Counter(),
        2: Counter(),
    }
    base_prefix = 0
    oracle_topk_independent_prefix = 0
    aligned_steps = 0
    aligned_first_choice = 0

    for group, rec in aligned:
        if len(group) < 3:
            continue
        draft_ids = rec["draft_ids"]
        target_ids = rec["target_ids"]
        if len(draft_ids) < 3 or len(target_ids) < 3:
            continue
        aligned_steps += 1
        base_prefix += accepted_len(draft_ids, target_ids)
        independent_oracle_ids = list(draft_ids)
        for pos in range(3):
            sampled = group[pos].get("sampled_token_ids") or []
            if sampled and int(sampled[0]) == draft_ids[pos]:
                aligned_first_choice += 1
            top_ids_rows = group[pos].get("top_token_ids") or []
            top_ids = [int(x) for x in (top_ids_rows[0] if top_ids_rows else [])]
            target = target_ids[pos]
            per_pos_attempts[pos] += 1
            if draft_ids[pos] == target:
                per_pos_match[pos] += 1
            if target in top_ids:
                rank = top_ids.index(target) + 1
                per_pos_in_topk[pos] += 1
                per_pos_rank_hist[pos][rank] += 1
                independent_oracle_ids[pos] = target
            else:
                per_pos_rank_hist[pos]["miss"] += 1
        oracle_topk_independent_prefix += accepted_len(
            independent_oracle_ids, target_ids)

    summary = {
        "classification": "diagnostic_only_draft_topk_join",
        "draft_topk": args.draft_topk,
        "verify_trace": args.verify_trace,
        "draft_rows": len(draft_rows),
        "draft_groups": len(groups),
        "verify_records": len(ver_rows),
        "alignment": {
            "method": "greedy_exact_sampled_draft_tuple",
            "first_choice_matches": aligned_first_choice,
            "first_choice_match_rate": (
                None if aligned_steps == 0 else aligned_first_choice /
                (aligned_steps * 3)
            ),
            **alignment_meta,
        },
        "steps": aligned_steps,
        "base_mean_target_tokens_per_step": (
            None if aligned_steps == 0 else 1.0 + base_prefix / aligned_steps
        ),
        "oracle_topk_independent_upper_bound": {
            "mean_target_tokens_per_step": (
                None
                if aligned_steps == 0
                else 1.0 + oracle_topk_independent_prefix / aligned_steps
            ),
            "runtime_interpretation": (
                "Diagnostic upper bound only. Not directly implementable for "
                "sequential MTP unless later draft positions are regenerated "
                "or a branch/tree drafter is made correct."
            ),
        },
        "oracle_topk_mean_target_tokens_per_step_deprecated": (
            None
            if aligned_steps == 0
            else 1.0 + oracle_topk_independent_prefix / aligned_steps
        ),
        "per_position": {
            str(pos): {
                "attempts": per_pos_attempts[pos],
                "current_match_rate": (
                    None if per_pos_attempts[pos] == 0 else
                    per_pos_match[pos] / per_pos_attempts[pos]
                ),
                "target_in_topk_rate": (
                    None if per_pos_attempts[pos] == 0 else
                    per_pos_in_topk[pos] / per_pos_attempts[pos]
                ),
                "rank_hist": {
                    str(rank): count
                    for rank, count in sorted(
                        per_pos_rank_hist[pos].items(),
                        key=lambda item: str(item[0]),
                    )
                },
            }
            for pos in range(3)
        },
    }

    text = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
