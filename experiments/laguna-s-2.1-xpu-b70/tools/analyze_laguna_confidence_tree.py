#!/usr/bin/env python3
"""Analyze the default-off Laguna confidence/tree diagnostic.

This tool emits projections only. It refuses to treat attribution-enabled timing
as benchmark evidence and joins a proposal only to the following outcome within
the same explicitly marked request.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any

SPECULATIVE_TOKENS = 11
RECORD_RATE = 125.4619731637751
RECORD_DRAFTS = 1609
RECORD_ACCEPTED = 4747
RECORD_EMITTED_PER_CYCLE = 1.0 + RECORD_ACCEPTED / RECORD_DRAFTS


def die(message: str) -> None:
    raise SystemExit(f"Laguna confidence-tree analyzer: {message}")


def load(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        die(f"cannot read {path}: {exc}")


def token_hash(row: dict[str, Any]) -> str:
    ids = row.get("token_ids")
    if not isinstance(ids, list) or not all(isinstance(value, int) for value in ids):
        die("benchmark row has no integer token_ids")
    return hashlib.sha256(",".join(str(value) for value in ids).encode()).hexdigest()


def validate_benchmark(candidate: dict[str, Any], reference: dict[str, Any]) -> None:
    candidate_rows = candidate.get("rows")
    reference_rows = reference.get("rows")
    if not isinstance(candidate_rows, list) or len(candidate_rows) != 13:
        die("candidate benchmark does not contain 13 rows")
    if not isinstance(reference_rows, list) or len(reference_rows) != 13:
        die("reference benchmark does not contain 13 rows")
    for index, (got, want) in enumerate(
        zip(candidate_rows, reference_rows, strict=True)
    ):
        for field in ("prompt_tokens", "completion_tokens"):
            if got.get(field) != want.get(field):
                die(f"benchmark row {index} {field} drift")
        if token_hash(got) != token_hash(want):
            die(f"benchmark row {index} generated token drift")
        usage = got.get("usage")
        details = (
            usage.get("prompt_tokens_details") if isinstance(usage, dict) else None
        )
        if not isinstance(details, dict) or details.get("cached_tokens") != 0:
            die(f"benchmark row {index} is not cache-zero")


def validate_rank_payloads(
    root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    payloads = [load(root / f"cycle-attribution-rank{rank}.json") for rank in range(4)]
    reference: list[dict[str, Any]] | None = None
    disagreements: list[dict[str, Any]] = []
    for rank, payload in enumerate(payloads):
        if payload.get("schema") != "laguna-cycle-attribution-v1":
            die(f"rank {rank} schema drift")
        if payload.get("status") != "complete" or not payload.get("diagnostic_only"):
            die(f"rank {rank} is not a completed diagnostic")
        if payload.get("not_benchmark_or_submission_evidence") is not True:
            die(f"rank {rank} lacks the non-benchmark marker")
        if payload.get("rank") != rank:
            die(f"rank {rank} identity drift")
        if payload.get("num_speculative_tokens") != SPECULATIVE_TOKENS:
            die(f"rank {rank} speculative depth drift")
        if payload.get("abandoned_cycles") != 0:
            die(f"rank {rank} has abandoned cycles")
        probe = payload.get("topk_probe")
        if not isinstance(probe, list) or not probe:
            die(f"rank {rank} has no confidence rows")
        if reference is None:
            reference = probe
        else:
            if len(probe) != len(reference):
                die(f"rank {rank} confidence row count differs from rank 0")
            for index, (rank0_row, rank_row) in enumerate(
                zip(reference, probe, strict=True)
            ):
                if rank_row != rank0_row:
                    disagreements.append(
                        {
                            "rank": rank,
                            "row": index,
                            "rank0": rank0_row,
                            "observed": rank_row,
                        }
                    )
    assert reference is not None
    return reference, disagreements


def joined_cycles(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    requests: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for index, proposal in enumerate(rows):
        has_previous = proposal.get("entry_has_previous_outcome")
        if has_previous is False:
            if current:
                requests.append(current)
            current = []
        elif has_previous is not True:
            die(f"cycle {index} has no explicit request-boundary marker")
        if index == 0 or has_previous is False:
            continue
        previous = rows[index - 1]
        if previous.get("cycle") + 1 != proposal.get("cycle"):
            die(f"cycle index drift at row {index}")
        positions = previous.get("positions")
        if not isinstance(positions, list) or len(positions) != 2:
            die(f"cycle {index - 1} lacks two draft positions")
        rejected = proposal.get("entry_num_rejected")
        if not isinstance(rejected, int) or not 0 <= rejected <= SPECULATIVE_TOKENS:
            die(f"cycle {index} rejection count drift")
        accepted = SPECULATIVE_TOKENS - rejected
        target = proposal.get("entry_next_token_id")
        if not isinstance(target, int):
            die(f"cycle {index} realised token drift")
        margins: list[float] = []
        top2: list[int] = []
        for position, row in enumerate(positions):
            if row.get("position") != position:
                die(f"cycle {index - 1} position order drift")
            margin = row.get("margin")
            if not isinstance(margin, (int, float)) or not math.isfinite(margin):
                die(f"cycle {index - 1} non-finite margin")
            if margin < 0:
                die(f"cycle {index - 1} negative margin")
            margins.append(float(margin))
            top2.append(int(row["top2"]))
        rescue0 = accepted == 0 and target == top2[0]
        rescue1 = accepted == 1 and target == top2[1]
        chain = accepted + 1
        one = chain + int(rescue0) - int(accepted == 11)
        two = chain + int(rescue0) + int(rescue1) - max(0, accepted - 9)
        current.append(
            {
                "accepted": accepted,
                "margin0": margins[0],
                "margin1": margins[1],
                "rescue0": rescue0,
                "rescue1": rescue1,
                "delta_one": one - chain,
                "delta_two": two - chain,
                "delta_oracle": max(chain, one, two) - chain,
            }
        )
    if current:
        requests.append(current)
    if len(requests) != 13 or any(not request for request in requests):
        die(f"expected 13 non-empty request groups, got {list(map(len, requests))}")
    return requests


def threshold_grid(rows: list[dict[str, Any]], key: str) -> list[float]:
    values = sorted(row[key] for row in rows)
    if not values:
        die("empty threshold training set")
    points = [-math.inf]
    for quantile in range(21):
        index = round((len(values) - 1) * quantile / 20)
        points.append(values[index])
    points.append(math.inf)
    return sorted(set(points))


def policy_delta(row: dict[str, Any], threshold0: float, threshold1: float) -> int:
    if row["margin0"] <= threshold0:
        return row["delta_one"]
    if row["margin1"] <= threshold1:
        return row["delta_two"]
    return 0


def fit_policy(rows: list[dict[str, Any]]) -> tuple[float, float, float]:
    best = (-math.inf, -math.inf, -math.inf)
    for threshold0 in threshold_grid(rows, "margin0"):
        for threshold1 in threshold_grid(rows, "margin1"):
            mean = statistics.fmean(
                policy_delta(row, threshold0, threshold1) for row in rows
            )
            candidate = (mean, -threshold0, -threshold1)
            if candidate > best:
                best = candidate
                chosen = (threshold0, threshold1)
    return chosen[0], chosen[1], best[0]


def projected_rate(mean_delta: float, overhead: float = 0.0) -> float:
    return (
        RECORD_RATE
        * (RECORD_EMITTED_PER_CYCLE + mean_delta)
        / RECORD_EMITTED_PER_CYCLE
        / (1.0 + overhead)
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--reference-bench", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        die("output already exists")

    identity = (args.run / "identity.txt").read_text()
    if (
        "confidence_probe=1\n" not in identity
        or "scored_measurement=0\n" not in identity
    ):
        die("run identity is not a non-scored confidence diagnostic")
    status = (args.run / "status.txt").read_text()
    if "status=PASS" not in status:
        die("diagnostic leg did not pass")
    candidate_bench = load(args.run / "bench.json")
    reference_bench = load(args.reference_bench)
    validate_benchmark(candidate_bench, reference_bench)
    probe_rows, rank_disagreements = validate_rank_payloads(
        args.run / "confidence-attribution"
    )
    requests = joined_cycles(probe_rows)
    rows = [row for request in requests for row in request]

    static_one = statistics.fmean(row["delta_one"] for row in rows)
    static_two = statistics.fmean(row["delta_two"] for row in rows)
    oracle = statistics.fmean(row["delta_oracle"] for row in rows)

    held_out: list[list[int]] = [[] for _ in requests]
    fold_thresholds: list[dict[str, float | int]] = []
    for held_out_index, request in enumerate(requests):
        training = [
            row
            for index, other in enumerate(requests)
            if index != held_out_index
            for row in other
        ]
        threshold0, threshold1, training_delta = fit_policy(training)
        held_out[held_out_index] = [
            policy_delta(row, threshold0, threshold1) for row in request
        ]
        fold_thresholds.append(
            {
                "prompt": held_out_index,
                "threshold0": threshold0,
                "threshold1": threshold1,
                "training_mean_delta": training_delta,
                "held_out_cycles": len(request),
                "held_out_mean_delta": statistics.fmean(held_out[held_out_index]),
            }
        )
    lopo_values = [value for request in held_out for value in request]
    lopo = statistics.fmean(lopo_values)

    rng = random.Random(20260731)
    bootstrap_rates: list[float] = []
    for _ in range(10_000):
        sampled = [rng.randrange(len(requests)) for _ in requests]
        numerator = sum(sum(held_out[index]) for index in sampled)
        denominator = sum(len(held_out[index]) for index in sampled)
        bootstrap_rates.append(projected_rate(numerator / denominator))
    bootstrap_rates.sort()

    per_prompt = []
    for index, request in enumerate(requests):
        per_prompt.append(
            {
                "prompt": index,
                "cycles": len(request),
                "position0_misses": sum(row["accepted"] == 0 for row in request),
                "position0_rescues": sum(row["rescue0"] for row in request),
                "position1_misses": sum(row["accepted"] == 1 for row in request),
                "position1_rescues": sum(row["rescue1"] for row in request),
                "oracle_mean_delta": statistics.fmean(
                    row["delta_oracle"] for row in request
                ),
                "lopo_mean_delta": statistics.fmean(held_out[index]),
            }
        )

    payload = {
        "schema": "laguna-confidence-tree-analysis-v1",
        "diagnostic_only": True,
        "not_benchmark_or_submission_evidence": True,
        "record": {
            "conventional_tok_s": RECORD_RATE,
            "draft_cycles": RECORD_DRAFTS,
            "accepted_draft_tokens": RECORD_ACCEPTED,
            "emitted_tokens_per_cycle": RECORD_EMITTED_PER_CYCLE,
        },
        "joined_cycles": len(rows),
        "request_cycles": [len(request) for request in requests],
        "rank0_canonical_for_screening_only": bool(rank_disagreements),
        "rank_disagreements": rank_disagreements,
        "counts": {
            "position0_misses": sum(row["accepted"] == 0 for row in rows),
            "position0_rescues": sum(row["rescue0"] for row in rows),
            "position1_misses": sum(row["accepted"] == 1 for row in rows),
            "position1_rescues": sum(row["rescue1"] for row in rows),
        },
        "static": {
            "one_alternate_mean_delta": static_one,
            "one_alternate_projected_tok_s": projected_rate(static_one),
            "two_alternate_mean_delta": static_two,
            "two_alternate_projected_tok_s": projected_rate(static_two),
        },
        "hindsight_oracle": {
            "mean_delta": oracle,
            "projected_tok_s": projected_rate(oracle),
        },
        "leave_one_prompt_out_policy": {
            "rule": "one if margin0<=t0; else two if margin1<=t1; else chain",
            "mean_delta": lopo,
            "projected_tok_s": projected_rate(lopo),
            "prompt_bootstrap_95pct_tok_s": [
                bootstrap_rates[249],
                bootstrap_rates[9749],
            ],
            "folds": fold_thresholds,
        },
        "overhead_sensitivity_tok_s": {
            str(overhead): projected_rate(lopo, overhead)
            for overhead in (0.0, 0.0025, 0.005, 0.01)
        },
        "per_prompt": per_prompt,
        "gate": {
            "oracle_requires_tok_s": 131.0,
            "observable_requires_tok_s": 130.5,
            "oracle_pass": projected_rate(oracle) >= 131.0,
            "observable_pass": projected_rate(lopo) >= 130.5,
            "rank_agreement_pass": not rank_disagreements,
            "integration_authorized": (
                projected_rate(oracle) >= 131.0
                and projected_rate(lopo) >= 130.5
                and not rank_disagreements
            ),
        },
    }
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload["gate"], sort_keys=True))
    print(f"analysis: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
