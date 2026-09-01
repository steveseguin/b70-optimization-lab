#!/usr/bin/env python3
"""Fail closed unless the published R53/R54 strict matrix matches raw evidence."""

from __future__ import annotations

import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "experiments/qwen38-27b-b70/data"
RESULT = DATA / "2026-09-01-qwen38-fp8-explicit-deterministic-matrix-r54-result.json"
TARGETS = (
    "qwen38-fp8-mtp0-explicit-deterministic-r54a-r50",
    "qwen38-fp8-mtp0-explicit-deterministic-r54c-r50",
)
CANDIDATES = (
    "qwen38-fp8-mtp1-explicit-deterministic-r53a",
    "qwen38-fp8-mtp1-explicit-deterministic-r53b",
)


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def metric(attempt: str) -> float:
    directory = DATA / attempt
    performance = load(directory / "performance.json")
    canaries = load(directory / "canaries.json")
    gate = performance["realistic_final_gate"]
    rows = performance["rows"]
    assert gate["passed"] is True, f"workload gate failed: {attempt}"
    assert len(rows) == 12, f"incomplete prompt suite: {attempt}"
    assert all(row["cached_tokens"] == 0 for row in rows), f"cached row: {attempt}"
    assert canaries["pass_all"] is True, f"canary failure: {attempt}"
    return performance["summary"][
        "class_balanced_tok_s_1_100_intervals_after_ttft"
    ]["median"]


def assert_comparison(path: Path) -> None:
    comparison = load(path)
    exact = comparison["comparison"]
    qualification = comparison["qualification"]
    assert exact["complete_token_arrays_exact"] is True, path
    assert exact["exact_prompts"] == exact["total_prompts"] == 12, path
    assert qualification["strict_pair_qualified"] is True, path


def main() -> None:
    result = load(RESULT)
    target_values = [metric(attempt) for attempt in TARGETS]
    candidate_values = [metric(attempt) for attempt in CANDIDATES]

    assert_comparison(DATA / TARGETS[1] / "compare-target-r54a-r50.json")
    assert_comparison(DATA / CANDIDATES[1] / "compare-candidate-r53a.json")
    for candidate in CANDIDATES:
        for target in TARGETS:
            target_suffix = target.removeprefix("qwen38-fp8-mtp0-explicit-deterministic-")
            assert_comparison(DATA / candidate / f"compare-target-{target_suffix}.json")

    target_center = sum(target_values) / len(target_values)
    candidate_center = sum(candidate_values) / len(candidate_values)
    relative = (candidate_center / target_center - 1.0) * 100.0
    assert math.isclose(
        result["mtp0_target"]["median_of_attempt_medians_tok_s"],
        target_center,
        rel_tol=0,
        abs_tol=1e-12,
    )
    assert math.isclose(
        result["mtp1_candidate"]["median_of_attempt_medians_tok_s"],
        candidate_center,
        rel_tol=0,
        abs_tol=1e-12,
    )
    assert math.isclose(
        result["treatment_effect"]["relative_percent"],
        relative,
        rel_tol=0,
        abs_tol=1e-12,
    )
    assert result["quality_gate"]["all_four_target_candidate_comparisons_exact"] is True
    print(
        "R53/R54 PASS: "
        f"MTP1={candidate_center:.6f} tok/s, "
        f"MTP0={target_center:.6f} tok/s, gain={relative:.4f}%"
    )


if __name__ == "__main__":
    main()
