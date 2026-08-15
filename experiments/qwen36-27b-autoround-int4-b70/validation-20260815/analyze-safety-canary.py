#!/usr/bin/env python3
"""Fail-closed token parity analysis for the focused GDN safety canary."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path
from typing import Any


MIN_TOKENS = {
    "holdout--arithmetic-reasoning": 7,
    "holdout--structured-extraction": 247,
    "holdout--concurrency-review": 382,
    "holdout--long-rollover-repository-audit": 392,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def digest_tokens(rows: dict[str, list[int]]) -> str:
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def read_arm(root: Path, name: str) -> dict[str, Any] | None:
    arm = root / name
    bench_path = arm / "data" / "bench.json"
    if not bench_path.is_file():
        return None
    bench = json.loads(bench_path.read_text())
    rows_raw = bench.get("rows", [])
    rows = {str(row["prompt_id"]): list(row.get("token_ids", []))
            for row in rows_raw}
    rates = [float(row["tok_s_1_100_intervals_after_ttft"])
             for row in rows_raw
             if row.get("tok_s_1_100_intervals_after_ttft") is not None]
    runner_code_path = arm / "runner.exit-code"
    runner_code = int(runner_code_path.read_text().strip()) \
        if runner_code_path.is_file() else None
    expected_ids = set(MIN_TOKENS)
    actual_ids = set(rows)
    cached_zero = all(int(row.get("cached_tokens", -1)) == 0
                      for row in rows_raw)
    lengths_ok = all(len(rows.get(prompt_id, [])) >= minimum
                     for prompt_id, minimum in MIN_TOKENS.items())
    fresh_valid = bool(bench.get("fresh_response_validity", {}).get("valid"))
    valid = (runner_code == 0 and len(rows_raw) == len(MIN_TOKENS)
             and actual_ids == expected_ids and cached_zero and lengths_ok
             and fresh_valid)
    return {
        "name": name,
        "valid": valid,
        "runner_exit_code": runner_code,
        "rows": len(rows_raw),
        "prompt_ids_exact": actual_ids == expected_ids,
        "cached_tokens_all_zero": cached_zero,
        "minimum_lengths_pass": lengths_ok,
        "fresh_response_validity": fresh_valid,
        "token_lengths": {key: len(value) for key, value in rows.items()},
        "token_digest": digest_tokens(rows),
        "median_tok_s_1_100_intervals_after_ttft": (
            statistics.median(rates) if rates else None),
        "tokens": rows,
    }


def compare(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    diffs: dict[str, Any] = {}
    for prompt_id in sorted(MIN_TOKENS):
        left_tokens = left["tokens"].get(prompt_id, [])
        right_tokens = right["tokens"].get(prompt_id, [])
        first = next((index for index, pair in enumerate(zip(left_tokens,
                                                              right_tokens))
                      if pair[0] != pair[1]), None)
        if first is None and len(left_tokens) != len(right_tokens):
            first = min(len(left_tokens), len(right_tokens))
        if first is not None:
            diffs[prompt_id] = {
                "first_difference": first,
                "left_token": left_tokens[first] if first < len(left_tokens) else None,
                "right_token": right_tokens[first] if first < len(right_tokens) else None,
                "left_length": len(left_tokens),
                "right_length": len(right_tokens),
            }
    return {"exact": not diffs, "differences": diffs}


def main() -> int:
    args = parse_args()
    names = ["target-01a", "spec-01a", "target-01b", "spec-01b"]
    arms = {name: arm for name in names
            if (arm := read_arm(args.root, name)) is not None}
    comparisons: dict[str, Any] = {}
    for label, left, right in (
        ("target-01a_vs_spec-01a", "target-01a", "spec-01a"),
        ("target-01a_vs_target-01b", "target-01a", "target-01b"),
        ("spec-01a_vs_spec-01b", "spec-01a", "spec-01b"),
        ("target-01b_vs_spec-01b", "target-01b", "spec-01b"),
    ):
        if left in arms and right in arms:
            comparisons[label] = compare(arms[left], arms[right])
    required = ["target-01a", "spec-01a"]
    first_pair_passed = (all(name in arms and arms[name]["valid"]
                             for name in required)
                         and comparisons.get("target-01a_vs_spec-01a", {})
                         .get("exact") is True)
    repeats_present = all(name in arms for name in names)
    repeat_passed = repeats_present and all(arm["valid"] for arm in arms.values()) \
        and all(value["exact"] for value in comparisons.values())
    result = {
        "schema": "qwen27-upstream-gdn-safety-canary-v1",
        "root": str(args.root),
        "arms": {name: {key: value for key, value in arm.items()
                         if key != "tokens"}
                 for name, arm in arms.items()},
        "comparisons": comparisons,
        "first_pair_passed": first_pair_passed,
        "repeats_present": repeats_present,
        "strict_passed": repeat_passed if repeats_present else first_pair_passed,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["strict_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
