#!/usr/bin/env python3
"""Measure a deterministic all-position DFlash mismatch-repair forest.

The primary path is the full top-1 DFlash block. Spare verifier rows add
alternative tokens at any primary-path depth, optionally followed by one or
more of the later marginal top-1 tokens. Unlike a target-aware oracle, branch
selection uses only proposal probabilities and is implementable from the
existing one-pass DFlash output.

This remains an optimistic coverage diagnostic: reported same-round-cost
throughput excludes the measured cost of verifying more than 16 target rows.
"""

import argparse
import importlib.util
import json
import math
from pathlib import Path


DDTREE_PATH = Path(__file__).with_name("analyze-muse-ddtree-prefix-trace.py")
DDTREE_SPEC = importlib.util.spec_from_file_location("muse_ddtree_trace", DDTREE_PATH)
DDTREE = importlib.util.module_from_spec(DDTREE_SPEC)
assert DDTREE_SPEC.loader is not None
DDTREE_SPEC.loader.exec_module(DDTREE)


def branch_score(position_candidates, depth, rank, suffix, ordering):
    row = position_candidates[depth][rank]
    top = position_candidates[depth][0]
    if ordering == "depth":
        return (-depth, -rank)
    if ordering == "probability":
        return (row["prob"], -depth, -rank)
    if ordering == "odds":
        denominator = max(top["prob"], 1e-45)
        return (row["prob"] / denominator, -depth, -rank)
    if ordering == "path_probability":
        score = math.log(max(row["prob"], 1e-45))
        end = min(len(position_candidates), depth + 1 + suffix)
        for next_depth in range(depth + 1, end):
            score += math.log(max(position_candidates[next_depth][0]["prob"], 1e-45))
        return (score, -depth, -rank)
    raise ValueError(f"unknown ordering: {ordering}")


def build_repair_forest(position_candidates, budget, alternatives, suffix, ordering):
    """Return child maps for a full top-1 spine plus scored repair branches."""
    child_maps = [dict()]
    if budget <= 0 or not position_candidates:
        return child_maps

    # Preserve the complete top-1 spine before spending any rows on repairs.
    spine_nodes = [0]
    for rows in position_candidates[:budget]:
        if not rows:
            break
        parent = spine_nodes[-1]
        node = len(child_maps)
        child_maps.append({})
        child_maps[parent][rows[0]["token"]] = node
        spine_nodes.append(node)

    branches = []
    for depth, rows in enumerate(position_candidates[: len(spine_nodes) - 1]):
        for rank in range(1, min(len(rows), alternatives + 1)):
            branch_suffix = min(suffix, len(position_candidates) - depth - 1)
            branches.append({
                "depth": depth,
                "rank": rank,
                "suffix": branch_suffix,
                "cost": 1 + branch_suffix,
                "score": branch_score(
                    position_candidates, depth, rank, branch_suffix, ordering
                ),
            })
    branches.sort(key=lambda row: row["score"], reverse=True)

    for branch in branches:
        if len(child_maps) - 1 + branch["cost"] > budget:
            continue
        depth = branch["depth"]
        parent = spine_nodes[depth]
        token = position_candidates[depth][branch["rank"]]["token"]
        if token in child_maps[parent]:
            continue
        node = len(child_maps)
        child_maps.append({})
        child_maps[parent][token] = node
        for next_depth in range(depth + 1, depth + 1 + branch["suffix"]):
            token = position_candidates[next_depth][0]["token"]
            next_node = len(child_maps)
            child_maps.append({})
            child_maps[node][token] = next_node
            node = next_node
    return child_maps


def repair_match_length(record, targets, budget, alternatives, suffix, ordering):
    child_maps = build_repair_forest(
        record["candidates"], budget, alternatives, suffix, ordering
    )
    node = 0
    matched = 0
    for target_pos in range(record["anchor"], record["anchor"] + record["drafted"]):
        token = targets.get(target_pos)
        if token is None or token not in child_maps[node]:
            break
        node = child_maps[node][token]
        matched += 1
    return matched


def analyze_request(request, label, round_ms, strategies):
    rows = {}
    for strategy in strategies:
        result = DDTREE.simulate(
            request,
            lambda record, targets, strategy=strategy: (
                0 if record is None else repair_match_length(
                    record,
                    targets,
                    strategy["budget"],
                    strategy["alternatives"],
                    strategy["suffix"],
                    strategy["ordering"],
                )
            ),
        )
        result["same_round_cost_tok_s"] = 1000.0 * result["emitted_tokens"] / (
            result["rounds"] * round_ms
        )
        result["max_round_ms_for_100"] = 10.0 * result["emitted_tokens"] / result["rounds"]
        rows[strategy["name"]] = result
    return {"label": label, "baseline_round_ms": round_ms, "strategies": rows}


def make_strategies(budgets, alternatives, suffixes, orderings):
    return [
        {
            "name": f"repair_b{budget}_a{alternative}_s{suffix}_{ordering}",
            "budget": budget,
            "alternatives": alternative,
            "suffix": suffix,
            "ordering": ordering,
        }
        for budget in budgets
        for alternative in alternatives
        for suffix in suffixes
        for ordering in orderings
    ]


def summarize(requests, strategies):
    rows = []
    for strategy in strategies:
        class_rows = [request["strategies"][strategy["name"]] for request in requests]
        rows.append({
            **strategy,
            "mean_same_round_cost_tok_s": sum(
                row["same_round_cost_tok_s"] for row in class_rows
            ) / len(class_rows),
            "per_class_rounds": {
                requests[i]["label"]: class_rows[i]["rounds"] for i in range(len(requests))
            },
            "per_class_max_round_ms_for_100": {
                requests[i]["label"]: class_rows[i]["max_round_ms_for_100"]
                for i in range(len(requests))
            },
        })
    rows.sort(key=lambda row: row["mean_same_round_cost_tok_s"], reverse=True)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("trace_log", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--labels", nargs="+", default=["prose", "code", "json"])
    parser.add_argument("--baseline-round-ms", nargs="+", type=float, default=[62.83, 61.61, 61.69])
    parser.add_argument("--budgets", nargs="+", type=int, default=[15, 22, 30, 32, 44, 48, 64])
    parser.add_argument("--alternatives", nargs="+", type=int, default=[1, 2, 3])
    parser.add_argument("--suffixes", nargs="+", type=int, default=[0, 1, 2])
    parser.add_argument(
        "--orderings", nargs="+",
        default=["depth", "probability", "odds", "path_probability"],
    )
    args = parser.parse_args()

    parsed = DDTREE.parse_trace(args.trace_log.read_text(errors="replace").splitlines())
    if not (len(parsed) == len(args.labels) == len(args.baseline_round_ms)):
        raise ValueError("request, label, and round-time counts differ")
    strategies = make_strategies(
        args.budgets, args.alternatives, args.suffixes, args.orderings
    )
    requests = [
        analyze_request(parsed[i], args.labels[i], args.baseline_round_ms[i], strategies)
        for i in range(len(parsed))
    ]
    result = {
        "schema": "muse_dflash_repair_forest_v1",
        "interpretation": (
            "Target-exact coverage of implementable DFlash top-1-spine repair forests. "
            "Same-round-cost throughput is an optimistic ceiling and excludes wider-batch cost."
        ),
        "requests": requests,
        "summary": summarize(requests, strategies),
    }
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
