#!/usr/bin/env python3
"""Measure DFlash/DSpark complementarity at identical target prefixes.

The input logs come from ``LLAMA_SPEC_PROPOSAL_TRACE_ONE_TOKEN=1`` with a
full verify-width target batch.  The server runs a complete proposal block at
every generated-token prefix, verifies it, then deliberately accepts zero
draft tokens.  That yields aligned proposal blocks without changing the target
batch arithmetic or canonical greedy stream.

This script simulates linear DFlash, linear DSpark, and an exact two-branch
ensemble that keeps whichever primary proposal matches the target for longer.
It is a ceiling diagnostic: it does not include the cost of running two
proposers or verifying a wider target batch.
"""

import argparse
import json
from pathlib import Path
import re


CANDIDATE_RE = re.compile(
    r"draft candidate\s+(?P<rank>\d+),\s+pos\s+(?P<pos>\d+):\s+"
    r"(?P<token>\d+)\s+\(\s*(?P<prob>[0-9.eE+-]+)\)"
)
ANCHOR_RE = re.compile(r"proposal trace anchor=(?P<anchor>\d+) drafted=(?P<drafted>\d+)")
TARGET_RE = re.compile(r"proposal trace target anchor=(?P<anchor>\d+) sampled=(?P<token>\d+)")
REQUEST_END_RE = re.compile(r"stop processing:")


def parse_trace(lines):
    candidates = {}
    pending = None
    requests = []
    records = []
    targets = {}

    def finish_request(line_no):
        nonlocal candidates, pending, records, targets
        if pending is not None:
            raise ValueError(f"line {line_no}: request ended with an unpaired proposal")
        if candidates:
            raise ValueError(f"line {line_no}: request ended with unassigned candidates")
        if records or targets:
            requests.append({"records": records, "targets": targets})
        records = []
        targets = {}
        candidates = {}

    for line_no, line in enumerate(lines, 1):
        match = CANDIDATE_RE.search(line)
        if match:
            rank = int(match.group("rank")) + 1
            pos = int(match.group("pos"))
            candidates.setdefault(pos, []).append({
                "rank": rank,
                "token": int(match.group("token")),
                "prob": float(match.group("prob")),
            })
            continue

        match = ANCHOR_RE.search(line)
        if match:
            if pending is not None:
                raise ValueError(f"line {line_no}: proposal before prior target marker")
            anchor = int(match.group("anchor"))
            drafted = int(match.group("drafted"))
            positions = [pos for pos in sorted(candidates) if candidates[pos]]
            if len(positions) < drafted:
                raise ValueError(
                    f"line {line_no}: only {len(positions)} candidate positions for {drafted} drafts"
                )
            positions = positions[:drafted]
            pending = {
                "anchor": anchor,
                "drafted": drafted,
                "primary": [candidates[pos][0] for pos in positions],
            }
            candidates = {}
            continue

        match = TARGET_RE.search(line)
        if match:
            anchor = int(match.group("anchor"))
            token = int(match.group("token"))
            if anchor in targets and targets[anchor] != token:
                raise ValueError(f"line {line_no}: conflicting target token at anchor {anchor}")
            targets[anchor] = token
            if pending is not None:
                if pending["anchor"] != anchor:
                    raise ValueError(
                        f"line {line_no}: target anchor {anchor} != proposal anchor {pending['anchor']}"
                    )
                pending["target_token"] = token
                records.append(pending)
                pending = None
            continue

        if REQUEST_END_RE.search(line):
            finish_request(line_no)

    if pending is not None or candidates:
        raise ValueError("trace ended with an incomplete proposal")
    if records or targets:
        finish_request(len(lines) + 1)
    return requests


def primary_tokens(record, p_min=None):
    result = []
    for item in record["primary"]:
        if p_min is not None and item["prob"] < p_min:
            break
        result.append(item["token"])
    return result


def match_length(tokens, targets, anchor):
    matched = 0
    for offset, token in enumerate(tokens):
        if targets.get(anchor + offset) != token:
            break
        matched += 1
    return matched


def simulate(records_by_anchor, targets, selector):
    if not targets:
        raise ValueError("request has no target tokens")
    last_anchor = max(targets)
    anchor = min(targets)
    rounds = 0
    accepted = 0
    choices = {"dflash": 0, "dspark": 0, "tie": 0, "none": 0}

    while anchor <= last_anchor:
        rounds += 1
        choice, matched = selector(anchor)
        choices[choice] = choices.get(choice, 0) + 1
        accepted += matched
        anchor += matched + 1

    return {
        "rounds": rounds,
        "accepted_tokens": accepted,
        "emitted_tokens": len(targets),
        "emitted_per_round": len(targets) / rounds,
        "choices": choices,
    }


def analyze_request(dflash, dspark, label, baseline_round_ms):
    if dflash["targets"] != dspark["targets"]:
        raise ValueError(f"{label}: DFlash and DSpark target streams differ")
    targets = dflash["targets"]
    d_records = {row["anchor"]: row for row in dflash["records"]}
    s_records = {row["anchor"]: row for row in dspark["records"]}

    def length(table, anchor, p_min=None):
        row = table.get(anchor)
        if row is None:
            return 0
        return match_length(primary_tokens(row, p_min), targets, anchor)

    strategies = {}
    strategies["dflash_p015"] = simulate(
        d_records, targets, lambda anchor: ("dflash", length(d_records, anchor, 0.15))
    )
    strategies["dflash_p000"] = simulate(
        d_records, targets, lambda anchor: ("dflash", length(d_records, anchor, 0.0))
    )
    strategies["dspark_p000"] = simulate(
        s_records, targets, lambda anchor: ("dspark", length(s_records, anchor, 0.0))
    )

    def ensemble_selector(anchor, d_p_min):
        d_len = length(d_records, anchor, d_p_min)
        s_len = length(s_records, anchor, 0.0)
        if d_len > s_len:
            return "dflash", d_len
        if s_len > d_len:
            return "dspark", s_len
        return ("tie" if d_len else "none"), d_len

    strategies["ensemble_dflash_p015"] = simulate(
        d_records, targets, lambda anchor: ensemble_selector(anchor, 0.15)
    )
    strategies["ensemble_dflash_p000"] = simulate(
        d_records, targets, lambda anchor: ensemble_selector(anchor, 0.0)
    )

    for row in strategies.values():
        row["same_round_cost_tok_s"] = 1000.0 * len(targets) / (row["rounds"] * baseline_round_ms)
        row["max_round_ms_for_100_tok_s"] = 10.0 * len(targets) / row["rounds"]
        row["max_cost_multiplier_for_100"] = (
            row["max_round_ms_for_100_tok_s"] / baseline_round_ms
        )

    return {
        "label": label,
        "target_tokens": len(targets),
        "target_sha256_16": __import__("hashlib").sha256(
            ",".join(str(targets[i]) for i in sorted(targets)).encode()
        ).hexdigest()[:16],
        "proposal_records": {"dflash": len(d_records), "dspark": len(s_records)},
        "baseline_round_ms": baseline_round_ms,
        "strategies": strategies,
    }


def summarize(requests):
    strategy_names = list(requests[0]["strategies"])
    result = {}
    for name in strategy_names:
        same_cost_rates = [request["strategies"][name]["same_round_cost_tok_s"] for request in requests]
        result[name] = {
            "mean_same_round_cost_tok_s": sum(same_cost_rates) / len(same_cost_rates),
            "per_class_same_round_cost_tok_s": {
                request["label"]: request["strategies"][name]["same_round_cost_tok_s"]
                for request in requests
            },
            "per_class_max_cost_multiplier_for_100": {
                request["label"]: request["strategies"][name]["max_cost_multiplier_for_100"]
                for request in requests
            },
        }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dflash_log", type=Path)
    parser.add_argument("dspark_log", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--labels", nargs="+", default=["prose", "code", "json"])
    parser.add_argument(
        "--baseline-round-ms", nargs="+", type=float, default=[62.83, 61.61, 61.69],
        help="retained per-class DFlash round times",
    )
    args = parser.parse_args()

    dflash = parse_trace(args.dflash_log.read_text(errors="replace").splitlines())
    dspark = parse_trace(args.dspark_log.read_text(errors="replace").splitlines())
    if not (len(dflash) == len(dspark) == len(args.labels) == len(args.baseline_round_ms)):
        raise ValueError(
            "request/label/round-time counts differ: "
            f"dflash={len(dflash)} dspark={len(dspark)} labels={len(args.labels)} "
            f"round_ms={len(args.baseline_round_ms)}"
        )

    requests = [
        analyze_request(dflash[i], dspark[i], args.labels[i], args.baseline_round_ms[i])
        for i in range(len(dflash))
    ]
    result = {
        "schema": "muse_dual_proposer_prefix_trace_v1",
        "interpretation": (
            "Proposal coverage is measured at every canonical target prefix with verify-width arithmetic. "
            "Same-round-cost throughput is an optimistic ceiling; real dual-proposer and wider-batch costs are excluded."
        ),
        "requests": requests,
        "summary": summarize(requests),
    }
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
