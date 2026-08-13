#!/usr/bin/env python3
"""Measure DFlash top-k coverage at the first target mismatch of each round.

Run llama-server with both ``-lv 5`` and ``LLAMA_TRACE=1``. DFlash already
logs its top three candidates at every proposed position, and the server logs
the accepted prefix length plus the target token sampled at the mismatch. This
parser joins those records without changing inference behavior.

The result is a branch-feasibility diagnostic, not a throughput claim: finding
the target token at rank 2/3 proves a compact tree could survive that mismatch,
but does not prove how many later tokens on that branch would also be accepted.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import re


CANDIDATE_RE = re.compile(
    r"draft candidate\s+(?P<rank>\d+),\s+pos\s+(?P<pos>\d+):\s+"
    r"(?P<token>\d+)\s+\(\s*(?P<prob>[0-9.eE+-]+)\)"
)
ACCEPT_RE = re.compile(r"accepted\s+(?P<accepted>\d+)\s*/\s*(?P<drafted>\d+)\s+draft tokens")
SAMPLED_RE = re.compile(r"add accepted tokens:\s+sampled=(?P<token>\d+)")
REQUEST_END_RE = re.compile(r"stop processing:")


def annotate_oracle_extensions(request):
    stream = []
    for row in request:
        row["stream_offset"] = len(stream)
        emitted = row["primary_draft"][:row["accepted"]] + [row["target_token"]]
        row["emitted_tokens"] = emitted
        stream.extend(emitted)

    for row in request:
        row["oracle_top1_suffix_extension"] = None
        if row["accepted"] >= row["drafted"] or row.get("target_rank") is None:
            continue
        stale_suffix = row["primary_draft"][row["accepted"] + 1:]
        future_offset = row["stream_offset"] + len(row["emitted_tokens"])
        extension = 0
        for candidate, target in zip(stale_suffix, stream[future_offset:]):
            if candidate != target:
                break
            extension += 1
        row["oracle_top1_suffix_extension"] = extension

    return stream


def summarize_rounds(rounds):
    rank_hist = Counter()
    mismatches = 0
    full_accepts = 0
    missing_position = 0
    inconsistent_top1 = 0
    extension_hist = Counter()

    for row in rounds:
        if row["accepted"] >= row["drafted"]:
            full_accepts += 1
            continue
        mismatches += 1
        rank = row.get("target_rank")
        if rank is None:
            missing_position += 1
        else:
            rank_hist[rank] += 1
            if rank == 1:
                inconsistent_top1 += 1
            extension = row.get("oracle_top1_suffix_extension")
            if extension is not None:
                extension_hist[extension] += 1

    def coverage(k):
        covered = sum(count for rank, count in rank_hist.items() if rank <= k)
        return {
            "count": covered,
            "fraction_of_mismatches": covered / mismatches if mismatches else None,
        }

    projections = {}
    baseline_emitted = sum(len(row.get("emitted_tokens", [])) for row in rounds)
    for top_k in (2, 3):
        for suffix_depth in (0, 1, 2, 3, 4):
            extra = 0
            covered = 0
            for row in rounds:
                rank = row.get("target_rank")
                extension = row.get("oracle_top1_suffix_extension")
                if rank is None or rank > top_k or extension is None:
                    continue
                covered += 1
                # The alternative token is already emitted by the linear
                # verifier. Evaluating it as a tree node guarantees the next
                # target token, plus any matching stale suffix tokens.
                extra += 1 + min(extension, suffix_depth)
            projections[f"top{top_k}_suffix{suffix_depth}"] = {
                "covered_mismatch_rounds": covered,
                "baseline_emitted_tokens": baseline_emitted,
                "oracle_extra_emitted_tokens": extra,
                "oracle_emitted_token_ratio": (
                    (baseline_emitted + extra) / baseline_emitted if baseline_emitted else None
                ),
            }

    return {
        "rounds": len(rounds),
        "full_accept_rounds": full_accepts,
        "mismatch_rounds": mismatches,
        "target_rank_histogram": {str(k): rank_hist[k] for k in sorted(rank_hist)},
        "top2_coverage": coverage(2),
        "top3_coverage": coverage(3),
        "missing_mismatch_position": missing_position,
        "inconsistent_target_at_rank1": inconsistent_top1,
        "oracle_top1_suffix_extension_histogram": {
            str(k): extension_hist[k] for k in sorted(extension_hist)
        },
        "oracle_branch_projections": projections,
    }


def parse_trace(lines):
    candidates = {}
    pending = None
    rounds = []
    requests = []

    for line_no, line in enumerate(lines, 1):
        match = CANDIDATE_RE.search(line)
        if match:
            rank = int(match.group("rank")) + 1
            pos = int(match.group("pos"))
            if rank == 1 and pos == 0 and candidates and pending is None:
                raise ValueError(f"line {line_no}: new DFlash block before prior round completed")
            candidates.setdefault(pos, []).append({
                "rank": rank,
                "token": int(match.group("token")),
                "prob": float(match.group("prob")),
            })
            continue

        match = ACCEPT_RE.search(line)
        if match:
            if pending is not None:
                raise ValueError(f"line {line_no}: accepted record before prior sampled record")
            pending = {
                "accepted": int(match.group("accepted")),
                "drafted": int(match.group("drafted")),
                "candidate_positions": len(candidates),
            }
            continue

        match = SAMPLED_RE.search(line)
        if match and pending is not None:
            target = int(match.group("token"))
            pending["target_token"] = target
            pending["primary_draft"] = [
                candidates[pos][0]["token"]
                for pos in sorted(candidates)
                if candidates[pos]
            ]
            if len(pending["primary_draft"]) != pending["drafted"]:
                raise ValueError(
                    f"line {line_no}: logged {len(pending['primary_draft'])} primary candidates "
                    f"for {pending['drafted']} drafted tokens"
                )
            if pending["accepted"] < pending["drafted"]:
                mismatch_pos = pending["accepted"]
                pending["mismatch_pos"] = mismatch_pos
                ranked = candidates.get(mismatch_pos, [])
                pending["target_rank"] = next(
                    (item["rank"] for item in ranked if item["token"] == target), None
                )
                pending["mismatch_candidates"] = ranked
            rounds.append(pending)
            pending = None
            candidates = {}
            continue

        if REQUEST_END_RE.search(line) and rounds:
            requests.append(rounds)
            rounds = []

    if pending is not None:
        raise ValueError("trace ended after accepted record but before sampled record")
    if candidates:
        raise ValueError("trace ended with an incomplete DFlash candidate block")
    if rounds:
        requests.append(rounds)

    streams = [annotate_oracle_extensions(request) for request in requests]
    all_rounds = [row for request in requests for row in request]
    return {
        "schema": "muse_dflash_topk_first_mismatch_v1",
        "interpretation": (
            "Coverage says whether the exact target mismatch token appeared in the logged "
            "DFlash top-k. It does not estimate acceptance after taking that branch."
        ),
        "overall": summarize_rounds(all_rounds),
        "requests": [
            {
                "request_index": i,
                "reconstructed_token_count": len(streams[i]),
                **summarize_rounds(request),
            }
            for i, request in enumerate(requests)
        ],
        "round_records": all_rounds,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = parse_trace(args.log.read_text(errors="replace").splitlines())
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
