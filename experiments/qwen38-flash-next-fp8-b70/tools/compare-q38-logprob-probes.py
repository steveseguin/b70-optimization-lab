#!/usr/bin/env python3
"""Compare two A59-style logprob probe files depth by depth.

For each depth present in both files: the first-step top-5 tokens and the
largest absolute top-1 logprob difference; then, along the first 128-token
repeat of each file, the first position whose token differs, the largest
absolute top-1 logprob difference before that position, and the candidate's
top-1/top-2 gap at the divergence. Prints JSON.

    compare-q38-logprob-probes.py --reference A76.json --candidate A84.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text())["results"]


def top1(entry) -> tuple[str, float]:
    token, logprob = entry[0]
    return token, float(logprob)


def compare_depth(ref: dict, cand: dict) -> dict:
    out: dict = {"prompt_sha256_match": ref["prompt_sha256"] == cand["prompt_sha256"]}
    r0 = ref["first_step"]["repeats"][0]
    c0 = cand["first_step"]["repeats"][0]
    r_top = r0["top_logprobs"][0]
    c_top = c0["top_logprobs"][0]
    out["first_step"] = {
        "reference_top5": [t for t, _ in r_top],
        "candidate_top5": [t for t, _ in c_top],
        "same_top1_token": r_top[0][0] == c_top[0][0],
        "top1_logprob_reference": float(r_top[0][1]),
        "top1_logprob_candidate": float(c_top[0][1]),
        "abs_top1_logprob_diff": abs(float(r_top[0][1]) - float(c_top[0][1])),
        "max_abs_diff_over_shared_top5": max(
            (abs(float(lr) - float(lc)) for tr, lr in r_top for tc, lc in c_top if tr == tc),
            default=None,
        ),
        "candidate_top1_top2_gap": abs(float(c_top[0][1]) - float(c_top[1][1])) if len(c_top) > 1 else None,
    }
    rf = ref["full"]["repeats"][0]
    cf = cand["full"]["repeats"][0]
    r_ids, c_ids = rf["output_token_ids"], cf["output_token_ids"]
    n = min(len(r_ids), len(c_ids))
    first = next((i for i in range(n) if r_ids[i] != c_ids[i]), None)
    limit = n if first is None else first
    diffs = [
        abs(float(rf["token_logprobs"][i]) - float(cf["token_logprobs"][i])) for i in range(limit)
    ]
    entry = {
        "positions_compared": n,
        "first_divergence_index": first,
        "max_abs_top1_logprob_diff_before_divergence": max(diffs) if diffs else 0.0,
        "mean_abs_top1_logprob_diff_before_divergence": (sum(diffs) / len(diffs)) if diffs else 0.0,
    }
    if first is not None:
        c_at = cf["top_logprobs"][first]
        r_at = rf["top_logprobs"][first]
        entry["candidate_top5_at_divergence"] = [[t, float(l)] for t, l in c_at]
        entry["reference_top5_at_divergence"] = [[t, float(l)] for t, l in r_at]
        entry["candidate_top1_top2_gap_at_divergence"] = (
            abs(float(c_at[0][1]) - float(c_at[1][1])) if len(c_at) > 1 else None
        )
        entry["reference_top1_top2_gap_at_divergence"] = (
            abs(float(r_at[0][1]) - float(r_at[1][1])) if len(r_at) > 1 else None
        )
    out["full_128"] = entry
    out["candidate_self_repeatable"] = len(cand["full"]["distinct_output_hashes"]) == 1 and cand["first_step"]["identical_top5"]
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reference", type=Path, required=True)
    ap.add_argument("--candidate", type=Path, required=True)
    args = ap.parse_args()
    ref, cand = load(args.reference), load(args.candidate)
    report = {
        "reference": str(args.reference),
        "candidate": str(args.candidate),
        "depths": {d: compare_depth(ref[d], cand[d]) for d in sorted(set(ref) & set(cand), key=int)},
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
