#!/usr/bin/env python3
"""Compare Laguna benchmark token streams against a deterministic teacher."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_run(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def first_diff(expected: list[int], actual: list[int]) -> dict[str, Any] | None:
    for index, (left, right) in enumerate(zip(expected, actual, strict=False)):
        if left != right:
            return {"index": index, "expected": left, "actual": right}
    if len(expected) != len(actual):
        return {
            "index": min(len(expected), len(actual)),
            "expected": expected[len(actual)] if len(expected) > len(actual) else None,
            "actual": actual[len(expected)] if len(actual) > len(expected) else None,
        }
    return None


def compare(teacher: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    teacher_rows = teacher["rows"]
    candidate_rows = candidate["rows"]
    results: list[dict[str, Any]] = []
    for index in range(max(len(teacher_rows), len(candidate_rows))):
        if index >= len(teacher_rows) or index >= len(candidate_rows):
            results.append(
                {
                    "index": index,
                    "exact": False,
                    "error": "row-count mismatch",
                }
            )
            continue
        expected = teacher_rows[index]
        actual = candidate_rows[index]
        expected_ids = [int(token) for token in expected.get("token_ids", [])]
        actual_ids = [int(token) for token in actual.get("token_ids", [])]
        diff = first_diff(expected_ids, actual_ids)
        identity_equal = all(
            expected.get(key) == actual.get(key)
            for key in ("prompt_index", "prompt_id", "prompt_sha256")
        )
        cached_zero = actual.get("cached_tokens") == 0
        results.append(
            {
                "index": index,
                "prompt_id": actual.get("prompt_id"),
                "prompt_tokens": actual.get("prompt_tokens"),
                "completion_tokens": actual.get("completion_tokens"),
                "identity_equal": identity_equal,
                "cached_tokens": actual.get("cached_tokens"),
                "cached_zero": cached_zero,
                "token_ids_equal": diff is None,
                "exact": identity_equal and cached_zero and diff is None,
                "first_diff": diff,
            }
        )

    exact_count = sum(bool(row["exact"]) for row in results)
    rollover = [row for row in results if int(row.get("prompt_tokens") or 0) >= 863]
    long_then_next = None
    if len(results) >= 2:
        long_then_next = {
            "long_prompt_id": results[0].get("prompt_id"),
            "long_completion_tokens": results[0].get("completion_tokens"),
            "long_exact": results[0].get("exact"),
            "next_prompt_id": results[1].get("prompt_id"),
            "next_exact": results[1].get("exact"),
            "passed": (
                results[0].get("completion_tokens") == 512
                and results[0].get("exact") is True
                and results[1].get("exact") is True
            ),
        }
    return {
        "exact": exact_count == len(results) == len(teacher_rows),
        "exact_count": exact_count,
        "total": len(results),
        "all_cached_zero": all(bool(row.get("cached_zero")) for row in results),
        "rollover": {
            "count": len(rollover),
            "exact_count": sum(bool(row["exact"]) for row in rollover),
            "rows": rollover,
        },
        "long_then_next": long_then_next,
        "rows": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--teacher", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    teacher = load_run(args.teacher)
    reports = []
    for candidate_path in args.candidate:
        reports.append(
            {
                "candidate": str(candidate_path.resolve()),
                "comparison": compare(teacher, load_run(candidate_path)),
            }
        )
    output = {
        "teacher": str(args.teacher.resolve()),
        "all_exact": all(report["comparison"]["exact"] for report in reports),
        "candidates": reports,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))
    return 0 if output["all_exact"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
