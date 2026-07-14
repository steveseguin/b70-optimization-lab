#!/usr/bin/env python3
"""Compare deterministic OpenAI logprob captures from two arithmetic lanes."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any


def token_key(item: dict[str, Any]) -> tuple[int, ...] | str:
    raw_bytes = item.get("bytes")
    if isinstance(raw_bytes, list):
        return tuple(int(value) for value in raw_bytes)
    return str(item.get("token"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    candidate_rows = {row["id"]: row for row in candidate["rows"]}
    position_rows = []
    chosen_matches = []
    top1_matches = []
    overlaps = []
    common_deltas = []

    for baseline_row in baseline["rows"]:
        candidate_row = candidate_rows[baseline_row["id"]]
        for position, (base_lp, cand_lp) in enumerate(
            zip(baseline_row["logprobs"], candidate_row["logprobs"], strict=False)
        ):
            base_top = {token_key(item): item["logprob"] for item in base_lp["top_logprobs"]}
            cand_top = {token_key(item): item["logprob"] for item in cand_lp["top_logprobs"]}
            common = base_top.keys() & cand_top.keys()
            deltas = [abs(base_top[key] - cand_top[key]) for key in common]
            overlap = len(common) / max(len(base_top), len(cand_top), 1)
            chosen_match = token_key(base_lp) == token_key(cand_lp)
            top1_match = token_key(base_lp["top_logprobs"][0]) == token_key(
                cand_lp["top_logprobs"][0]
            )
            chosen_matches.append(chosen_match)
            top1_matches.append(top1_match)
            overlaps.append(overlap)
            common_deltas.extend(deltas)
            position_rows.append(
                {
                    "id": baseline_row["id"],
                    "position": position,
                    "chosen_match": chosen_match,
                    "top1_match": top1_match,
                    "topk_overlap": overlap,
                    "common_token_count": len(common),
                    "common_logprob_abs_delta_mean": (
                        statistics.fmean(deltas) if deltas else None
                    ),
                }
            )

    summary = {
        "baseline": str(args.baseline),
        "candidate": str(args.candidate),
        "baseline_label": baseline.get("label"),
        "candidate_label": candidate.get("label"),
        "positions_compared": len(position_rows),
        "chosen_token_match_rate": statistics.fmean(chosen_matches),
        "top1_match_rate": statistics.fmean(top1_matches),
        "mean_topk_overlap": statistics.fmean(overlaps),
        "mean_common_logprob_abs_delta": statistics.fmean(common_deltas),
        "positions": position_rows,
    }
    rendered = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
