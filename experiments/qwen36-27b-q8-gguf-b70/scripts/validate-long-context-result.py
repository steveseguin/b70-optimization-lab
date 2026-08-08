#!/usr/bin/env python3
"""Fail closed on the calibrated Q8_0 long-context result."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--ctx-size", type=int, required=True)
    parser.add_argument("--max-tokens", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    suite = json.loads(args.suite.read_text())
    result = json.loads(args.result.read_text())
    expected = {case["id"]: case for case in suite["cases"]}
    rows = result.get("rows")
    if not isinstance(rows, list):
        raise SystemExit("result rows are missing")

    checks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        case_id = row.get("case_id")
        case = expected.get(case_id)
        prompt_tokens = row.get("prompt_tokens")
        completion_tokens = row.get("completion_tokens")
        calibrated = case.get("calibrated_prompt_tokens") if case else None
        check = {
            "case_id": case_id,
            "known_case": case is not None,
            "unique_case": isinstance(case_id, str) and case_id not in seen,
            "prompt_tokens": prompt_tokens,
            "calibrated_prompt_tokens": calibrated,
            "prompt_tokens_exact": prompt_tokens == calibrated,
            "completion_tokens": completion_tokens,
            "completion_tokens_positive": (
                isinstance(completion_tokens, int) and completion_tokens > 0
            ),
            "requested_limit_fits_context": (
                isinstance(prompt_tokens, int)
                and prompt_tokens + args.max_tokens <= args.ctx_size
            ),
            "actual_total_fits_context": (
                isinstance(prompt_tokens, int)
                and isinstance(completion_tokens, int)
                and prompt_tokens + completion_tokens <= args.ctx_size
            ),
            "retrieval_exact": bool((row.get("validation") or {}).get("pass")),
            "cached_tokens_zero": row.get("cached_tokens") == 0,
        }
        if isinstance(case_id, str):
            seen.add(case_id)
        check["passed"] = all(
            value is True
            for key, value in check.items()
            if key
            in {
                "known_case",
                "unique_case",
                "prompt_tokens_exact",
                "completion_tokens_positive",
                "requested_limit_fits_context",
                "actual_total_fits_context",
                "retrieval_exact",
                "cached_tokens_zero",
            }
        )
        checks.append(check)

    selected_ids = (result.get("run_identity") or {}).get("case_ids")
    selected_ids_match = (
        isinstance(selected_ids, list)
        and selected_ids == [check["case_id"] for check in checks]
    )
    passed = bool(checks) and selected_ids_match and all(
        check["passed"] for check in checks
    )
    output = {
        "passed": passed,
        "ctx_size": args.ctx_size,
        "max_tokens": args.max_tokens,
        "selected_ids_match": selected_ids_match,
        "checks": checks,
    }
    args.out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"out": str(args.out), "passed": passed}, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
