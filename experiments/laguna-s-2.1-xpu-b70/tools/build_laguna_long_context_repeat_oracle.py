#!/usr/bin/env python3
"""Build a fail-closed long-context repeat oracle from sealed bench packets."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


IDENTITY_FIELDS = (
    "prompt_token_ids_sha256",
    "output_token_ids_sha256",
    "text_sha256",
    "token_ids",
)
REQUIRED_REPEAT_CHECKS = {
    "cache_zero",
    "completion_length_exact",
    "decode_metric_count_one",
    "finish_reason_length",
    "first_100_timed",
    "prefill_metric_count_one",
    "prefill_metric_tokens_exact",
    "prefill_token_metric_count_one",
    "prompt_length_exact",
    "retrieval_pass",
    "returned_prompt_ids_exact",
    "stream_token_ids_exact",
}
ALLOWED_REPEAT_CHECKS = REQUIRED_REPEAT_CHECKS | {
    "oracle_exact_if_requested",
    "spec_position_counter_consistent",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repeat_eligible(row: dict[str, Any]) -> bool:
    checks = row.get("checks")
    if (
        not isinstance(row.get("passed"), bool)
        or not isinstance(checks, dict)
        or not REQUIRED_REPEAT_CHECKS.issubset(checks)
        or not set(checks).issubset(ALLOWED_REPEAT_CHECKS)
        or "oracle_exact_if_requested" not in checks
    ):
        return False
    if not all(checks[name] is True for name in REQUIRED_REPEAT_CHECKS):
        return False
    if (
        "spec_position_counter_consistent" in checks
        and checks["spec_position_counter_consistent"] is not True
    ):
        return False
    if row["passed"]:
        return all(value is True for value in checks.values())
    return checks.get("oracle_exact_if_requested") is False and all(
        value is True
        for name, value in checks.items()
        if name != "oracle_exact_if_requested"
    )


def load_row(path: Path, case_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = json.loads(path.read_text())
    created_at_utc = payload.get("run_identity", {}).get("created_at_utc")
    if not isinstance(created_at_utc, str) or not created_at_utc:
        raise SystemExit(f"source run identity is missing created_at_utc: {path}")
    rows = [row for row in payload.get("rows", []) if row.get("case_id") == case_id]
    if len(rows) != 1:
        raise SystemExit(f"expected one {case_id} row in {path}, found {len(rows)}")
    row = rows[0]
    if not repeat_eligible(row):
        raise SystemExit(f"source row failed an intrinsic gate: {path}: {case_id}")
    missing = [field for field in IDENTITY_FIELDS if field not in row]
    if missing:
        raise SystemExit(f"source row missing {missing}: {path}: {case_id}")
    if (
        not all(
            isinstance(row[field], str) and bool(row[field])
            for field in IDENTITY_FIELDS[:-1]
        )
        or not isinstance(row["token_ids"], list)
        or not row["token_ids"]
    ):
        raise SystemExit(f"source row has invalid identity fields: {path}: {case_id}")
    source = {
        "path": str(path.resolve()),
        "sha256": sha256(path),
        "status": payload.get("status"),
        "row_passed": row["passed"],
        "run_created_at_utc": created_at_utc,
    }
    return row, source


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--case-source",
        action="append",
        required=True,
        metavar="CASE_ID=PATH[,PATH]",
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    rows = []
    cases = []
    seen = set()
    for assignment in args.case_source:
        if "=" not in assignment:
            raise SystemExit("--case-source must be CASE_ID=PATH[,PATH]")
        case_id, paths_text = assignment.split("=", 1)
        if not case_id or case_id in seen:
            raise SystemExit(f"empty or duplicate case ID: {case_id}")
        seen.add(case_id)
        paths = [Path(value) for value in paths_text.split(",") if value]
        if not paths:
            raise SystemExit(f"no source paths for {case_id}")
        loaded = [load_row(path, case_id) for path in paths]
        resolved_paths = [str(path.resolve()) for path in paths]
        source_hashes = [source["sha256"] for _, source in loaded]
        source_run_times = [source["run_created_at_utc"] for _, source in loaded]
        if len(loaded) > 1 and (
            len(set(resolved_paths)) != len(resolved_paths)
            or len(set(source_hashes)) != len(source_hashes)
            or len(set(source_run_times)) != len(source_run_times)
        ):
            raise SystemExit(f"repeat sources are not independent: {case_id}")
        row = loaded[0][0]
        if any(
            other[field] != row[field]
            for other, _ in loaded[1:]
            for field in IDENTITY_FIELDS
        ):
            raise SystemExit(f"conflicting duplicate oracle row: {case_id}")
        if not row.get("passed") and len(loaded) < 2:
            raise SystemExit(
                f"non-passing prior-oracle row needs two repeat sources: {case_id}"
            )
        rows.append(row)
        cases.append(
            {
                "case_id": case_id,
                "sources": [source for _, source in loaded],
            }
        )

    result = {
        "schema": "laguna-long-context-repeat-oracle-v1",
        "status": "PASS_COMPOSITE_ORACLE",
        "case_ids": [case["case_id"] for case in cases],
        "cases": cases,
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "rows": len(rows)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
