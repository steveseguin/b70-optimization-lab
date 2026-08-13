#!/usr/bin/env python3
"""Target-aware upper bound for confidence-adaptive DFlash verify width."""

import argparse
import importlib.util
import json
from pathlib import Path


TRACE_PATH = Path(__file__).with_name("analyze-muse-ddtree-prefix-trace.py")
TRACE_SPEC = importlib.util.spec_from_file_location("muse_ddtree_trace", TRACE_PATH)
TRACE = importlib.util.module_from_spec(TRACE_SPEC)
assert TRACE_SPEC.loader is not None
TRACE_SPEC.loader.exec_module(TRACE)


def load_costs(path):
    rows = json.loads(path.read_text())
    return {int(row["n_prompt"]): float(row["avg_ns"]) / 1e6 for row in rows}


def interpolate_cost(costs, width):
    if width in costs:
        return costs[width]
    keys = sorted(costs)
    lower = max(key for key in keys if key < width)
    upper = min(key for key in keys if key > width)
    fraction = (width - lower) / (upper - lower)
    return costs[lower] + fraction * (costs[upper] - costs[lower])


def top1_match_length(record, targets):
    if record is None:
        return 0
    matched = 0
    for offset, rows in enumerate(record["candidates"]):
        if not rows or targets.get(record["anchor"] + offset) != rows[0]["token"]:
            break
        matched += 1
    return matched


def oracle_adaptive_width(request, costs, fixed_ms, max_draft=15):
    """Minimize total time while illegitimately knowing every future mismatch.

    Because a real confidence policy cannot know the target match length, this
    dynamic program is a strict coverage/cost upper bound for width selection.
    """
    targets = request["targets"]
    records = {record["anchor"]: record for record in request["records"]}
    first = min(targets)
    last = max(targets)
    dp = {last + 1: 0.0}
    choices = {}

    for anchor in range(last, first - 1, -1):
        match = top1_match_length(records.get(anchor), targets)
        candidates = []
        for draft_width in range(max_draft + 1):
            emitted = min(match, draft_width) + 1
            next_anchor = min(last + 1, anchor + emitted)
            time_ms = fixed_ms + interpolate_cost(costs, draft_width + 1) + dp[next_anchor]
            candidates.append((time_ms, draft_width, emitted, next_anchor, match))
        best = min(candidates)
        dp[anchor] = best[0]
        choices[anchor] = best

    anchor = first
    rounds = 0
    drafted = 0
    accepted = 0
    width_histogram = {}
    while anchor <= last:
        _, draft_width, emitted, next_anchor, match = choices[anchor]
        rounds += 1
        drafted += draft_width
        accepted += min(match, draft_width)
        width_histogram[str(draft_width)] = width_histogram.get(str(draft_width), 0) + 1
        anchor = next_anchor
    return {
        "rounds": rounds,
        "drafted_tokens": drafted,
        "accepted_tokens": accepted,
        "total_ms": dp[first],
        "tok_s": 1000.0 * len(targets) / dp[first],
        "width_histogram": width_histogram,
    }


def evaluate(requests, labels, round_ms, costs, fixed_scale):
    rows = []
    for request, label, incumbent_ms in zip(requests, labels, round_ms):
        # This deliberately assumes every incumbent round pays the measured
        # width-16 target cost. It therefore minimizes the inferred non-target
        # overhead and makes the adaptive oracle more optimistic.
        fixed_ms = max(0.0, incumbent_ms - interpolate_cost(costs, 16)) * fixed_scale
        result = oracle_adaptive_width(request, costs, fixed_ms)
        result.update({"label": label, "fixed_ms_per_round": fixed_ms})
        rows.append(result)
    return {
        "fixed_overhead_scale": fixed_scale,
        "mean_tok_s": sum(row["tok_s"] for row in rows) / len(rows),
        "requests": rows,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("trace_log", type=Path)
    parser.add_argument("cost_json", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--labels", nargs="+", default=["prose", "code", "json"])
    parser.add_argument("--round-ms", nargs="+", type=float, default=[62.83, 61.61, 61.69])
    args = parser.parse_args()

    requests = TRACE.parse_trace(args.trace_log.read_text(errors="replace").splitlines())
    if not (len(requests) == len(args.labels) == len(args.round_ms)):
        raise ValueError("request, label, and round-time counts differ")
    costs = load_costs(args.cost_json)
    scales = [1.0, 0.75, 0.5, 0.25, 0.0]
    evaluations = [evaluate(requests, args.labels, args.round_ms, costs, scale) for scale in scales]

    lower = 0.0
    upper = 1.0
    for _ in range(60):
        midpoint = (lower + upper) / 2
        if evaluate(requests, args.labels, args.round_ms, costs, midpoint)["mean_tok_s"] >= 100:
            lower = midpoint
        else:
            upper = midpoint
    required = evaluate(requests, args.labels, args.round_ms, costs, lower)
    result = {
        "schema": "muse_adaptive_verify_width_oracle_v1",
        "interpretation": (
            "Target-aware dynamic-programming upper bound. A real confidence policy must be no better. "
            "Target costs are measured TP4 llama-bench values; fixed overhead is inferred optimistically."
        ),
        "target_cost_ms": {str(key): costs[key] for key in sorted(costs)},
        "evaluations": evaluations,
        "fixed_overhead_scale_for_100": lower,
        "fixed_overhead_fraction_that_must_be_removed_for_100": 1.0 - lower,
        "required_case": required,
    }
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
