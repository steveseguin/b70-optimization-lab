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


def compare(
    teacher: dict[str, Any],
    candidate: dict[str, Any],
    *,
    text_oracle: dict[str, Any] | None = None,
    require_text_hash: bool = False,
) -> dict[str, Any]:
    teacher_rows = teacher["rows"]
    candidate_rows = candidate["rows"]
    text_rows = text_oracle["rows"] if text_oracle is not None else None
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
        expected_text_hash = expected.get("sha256")
        if expected_text_hash is None and text_rows is not None:
            if index >= len(text_rows):
                expected_text_hash = None
            else:
                text_expected = text_rows[index]
                if any(
                    text_expected.get(key) != expected.get(key)
                    for key in ("prompt_index", "prompt_id")
                ):
                    expected_text_hash = None
                else:
                    expected_text_hash = text_expected.get("sha256")
        expected_ids = [int(token) for token in expected.get("token_ids", [])]
        actual_ids = [int(token) for token in actual.get("token_ids", [])]
        diff = first_diff(expected_ids, actual_ids)
        identity_equal = all(
            expected.get(key) == actual.get(key)
            for key in ("prompt_index", "prompt_id", "prompt_sha256")
        )
        cached_zero = actual.get("cached_tokens") == 0
        text_hash_present = isinstance(expected_text_hash, str)
        text_sha256_equal = (
            actual.get("sha256") == expected_text_hash
            if text_hash_present
            else None
        )
        text_gate = (
            text_sha256_equal is True
            if require_text_hash or text_hash_present
            else True
        )
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
                "expected_text_sha256": expected_text_hash,
                "actual_text_sha256": actual.get("sha256"),
                "text_sha256_equal": text_sha256_equal,
                "exact": (
                    identity_equal
                    and cached_zero
                    and diff is None
                    and text_gate
                ),
                "first_diff": diff,
            }
        )

    exact_count = sum(bool(row["exact"]) for row in results)
    rollover = [row for row in results if int(row.get("prompt_tokens") or 0) >= 863]
    full512_then_next = None
    if len(results) >= 2:
        full512_then_next = {
            "first_prompt_id": results[0].get("prompt_id"),
            "first_completion_tokens": results[0].get("completion_tokens"),
            "first_exact": results[0].get("exact"),
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
        "text_sha256_checked_count": sum(
            row.get("text_sha256_equal") is not None for row in results
        ),
        "all_text_sha256_equal": all(
            row.get("text_sha256_equal") is True for row in results
        ),
        "rollover": {
            "count": len(rollover),
            "exact_count": sum(bool(row["exact"]) for row in rollover),
            "rows": rollover,
        },
        "full512_then_next": full512_then_next,
        # Backward-compatible key. This has always meant a 512-output-token
        # first request followed by the next request, not a long input prompt.
        "long_then_next": full512_then_next,
        "rows": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--teacher", type=Path, required=True)
    parser.add_argument("--teacher-text-oracle", type=Path)
    parser.add_argument("--require-text-hash", action="store_true")
    parser.add_argument("--candidate", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    teacher = load_run(args.teacher)
    text_oracle = (
        load_run(args.teacher_text_oracle)
        if args.teacher_text_oracle is not None
        else None
    )
    reports = []
    for candidate_path in args.candidate:
        reports.append(
            {
                "candidate": str(candidate_path.resolve()),
                "comparison": compare(
                    teacher,
                    load_run(candidate_path),
                    text_oracle=text_oracle,
                    require_text_hash=args.require_text_hash,
                ),
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
