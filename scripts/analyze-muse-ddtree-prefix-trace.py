#!/usr/bin/env python3
"""Estimate exact greedy DDTree coverage from a canonical DFlash prefix trace.

The trace is produced by ``LLAMA_SPEC_PROPOSAL_TRACE_ONE_TOKEN=1``.  It runs a
full-width DFlash proposal/target verification at every canonical target
prefix, but deliberately commits only one target token.  DDTree's proposal
tree depends only on the DFlash per-position marginal distributions, so the
canonical greedy continuation is sufficient to determine how far the target
would walk through that tree.

This is a ceiling diagnostic.  It excludes the cost increase from verifying a
larger tree batch and, for old traces, is limited to the candidate ranks and
probability precision present in the log.
"""

import argparse
import hashlib
import heapq
import json
import math
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
    requests = []
    records = []
    targets = {}
    candidates = {}
    pending = None

    def finish_request(line_no):
        nonlocal records, targets, candidates, pending
        if pending is not None:
            raise ValueError(f"line {line_no}: request ended with an unpaired proposal")
        if candidates:
            raise ValueError(f"line {line_no}: request ended with unassigned candidates")
        if records or targets:
            requests.append({"records": records, "targets": targets})
        records = []
        targets = {}
        candidates = {}
        pending = None

    for line_no, line in enumerate(lines, 1):
        match = CANDIDATE_RE.search(line)
        if match:
            pos = int(match.group("pos"))
            candidates.setdefault(pos, []).append({
                "rank": int(match.group("rank")),
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
            positions = sorted(candidates)
            if len(positions) < drafted:
                raise ValueError(
                    f"line {line_no}: only {len(positions)} candidate positions for {drafted} drafts"
                )
            pending = {
                "anchor": anchor,
                "drafted": drafted,
                "candidates": [
                    sorted(candidates[pos], key=lambda row: row["rank"])
                    for pos in positions[:drafted]
                ],
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


def build_child_maps(position_candidates, budget):
    """Mirror the official DDTree best-first heap construction."""
    child_maps = [dict()]
    if budget <= 0 or not position_candidates:
        return child_maps

    n_ranks = min(len(rows) for rows in position_candidates)
    if n_ranks <= 0:
        return child_maps

    def logp(depth, rank):
        prob = position_candidates[depth][rank]["prob"]
        return math.log(prob) if prob > 0.0 else -math.inf

    first_logw = logp(0, 0)
    # Official tuple ordering uses path ranks as a deterministic tie breaker.
    heap = [(-first_logw, (0,), 0, 1, 0, first_logw)]
    node_count = 0
    depth_limit = len(position_candidates)

    while heap and node_count < budget:
        _, ranks, parent_index, depth, rank, weight = heapq.heappop(heap)
        token = position_candidates[depth - 1][rank]["token"]
        current_index = node_count + 1
        child_maps.append({})
        child_maps[parent_index][token] = current_index
        node_count += 1

        if rank + 1 < n_ranks:
            old = logp(depth - 1, rank)
            new = logp(depth - 1, rank + 1)
            sibling_weight = weight - old + new if math.isfinite(old) else new
            heapq.heappush(
                heap,
                (-sibling_weight, ranks[:-1] + (rank + 1,), parent_index, depth, rank + 1, sibling_weight),
            )

        if depth < depth_limit:
            child_weight = weight + logp(depth, 0)
            heapq.heappush(
                heap,
                (-child_weight, ranks + (0,), current_index, depth + 1, 0, child_weight),
            )

    return child_maps


def tree_match_length(record, targets, budget):
    child_maps = build_child_maps(record["candidates"], budget)
    node = 0
    matched = 0
    for target_pos in range(record["anchor"], record["anchor"] + record["drafted"]):
        token = targets.get(target_pos)
        if token is None or token not in child_maps[node]:
            break
        node = child_maps[node][token]
        matched += 1
    return matched


def linear_match_length(record, targets, p_min):
    matched = 0
    for offset, rows in enumerate(record["candidates"]):
        if not rows or rows[0]["prob"] < p_min:
            break
        if targets.get(record["anchor"] + offset) != rows[0]["token"]:
            break
        matched += 1
    return matched


def simulate(request, selector):
    targets = request["targets"]
    records = {record["anchor"]: record for record in request["records"]}
    anchor = min(targets)
    last_anchor = max(targets)
    rounds = 0
    accepted = 0
    while anchor <= last_anchor:
        rounds += 1
        matched = selector(records.get(anchor), targets)
        accepted += matched
        anchor += matched + 1
    return {
        "rounds": rounds,
        "accepted_tokens": accepted,
        "emitted_tokens": len(targets),
        "emitted_per_round": len(targets) / rounds,
    }


def analyze_request(request, label, baseline_round_ms, budgets):
    linear = simulate(
        request,
        lambda record, targets: 0 if record is None else linear_match_length(record, targets, 0.15),
    )
    strategies = {"linear_p015": linear}
    for budget in budgets:
        strategies[f"ddtree_b{budget}"] = simulate(
            request,
            lambda record, targets, budget=budget: (
                0 if record is None else tree_match_length(record, targets, budget)
            ),
        )

    for row in strategies.values():
        row["same_round_cost_tok_s"] = 1000.0 * len(request["targets"]) / (row["rounds"] * baseline_round_ms)
        row["max_round_ms_for_100_tok_s"] = 10.0 * len(request["targets"]) / row["rounds"]
        row["max_cost_multiplier_for_100"] = row["max_round_ms_for_100_tok_s"] / baseline_round_ms

    ranks = {
        len(position)
        for record in request["records"]
        for position in record["candidates"]
    }
    return {
        "label": label,
        "target_tokens": len(request["targets"]),
        "target_sha256_16": hashlib.sha256(
            ",".join(str(request["targets"][i]) for i in sorted(request["targets"])).encode()
        ).hexdigest()[:16],
        "proposal_records": len(request["records"]),
        "candidate_ranks_present": sorted(ranks),
        "baseline_round_ms": baseline_round_ms,
        "strategies": strategies,
    }


def summarize(requests):
    result = {}
    for name in requests[0]["strategies"]:
        rows = [request["strategies"][name] for request in requests]
        result[name] = {
            "mean_same_round_cost_tok_s": sum(row["same_round_cost_tok_s"] for row in rows) / len(rows),
            "mean_emitted_per_round": sum(row["emitted_per_round"] for row in rows) / len(rows),
            "per_class_rounds": {
                request["label"]: request["strategies"][name]["rounds"] for request in requests
            },
            "per_class_max_round_ms_for_100": {
                request["label"]: request["strategies"][name]["max_round_ms_for_100_tok_s"]
                for request in requests
            },
        }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("trace_log", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--labels", nargs="+", default=["prose", "code", "json"])
    parser.add_argument("--baseline-round-ms", nargs="+", type=float, default=[62.83, 61.61, 61.69])
    parser.add_argument("--budgets", nargs="+", type=int, default=[15, 16, 22, 32, 48, 64])
    args = parser.parse_args()

    parsed = parse_trace(args.trace_log.read_text(errors="replace").splitlines())
    if not (len(parsed) == len(args.labels) == len(args.baseline_round_ms)):
        raise ValueError(
            f"request/label/round-time counts differ: requests={len(parsed)} "
            f"labels={len(args.labels)} round_ms={len(args.baseline_round_ms)}"
        )
    requests = [
        analyze_request(parsed[i], args.labels[i], args.baseline_round_ms[i], args.budgets)
        for i in range(len(parsed))
    ]
    result = {
        "schema": "muse_ddtree_prefix_trace_v1",
        "interpretation": (
            "Exact greedy target-path coverage under the official DDTree best-first construction. "
            "Same-round-cost throughput excludes wider target verification cost. Candidate ranks and "
            "probability precision are limited by the input trace."
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
