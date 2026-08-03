#!/usr/bin/env python3
"""Fail-closed analysis of Laguna's long-context mixed-depth feasibility run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


WARMUP_ID = "laguna-lc-01024-early"
LONG_IDS = (
    "laguna-lc-32640-early",
    "laguna-lc-32640-middle",
    "laguna-lc-32640-late",
)
SENTINEL_IDS = tuple(f"sentinel-after-{case_id}" for case_id in LONG_IDS)
EXPECTED_ROW_IDS = (WARMUP_ID,) + tuple(
    item for pair in zip(LONG_IDS, SENTINEL_IDS, strict=True) for item in pair
)
EXPECTED_POSITIONS = {str(position) for position in range(11)}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def position_counts(row: dict[str, Any]) -> dict[str, float]:
    values = row.get("spec_decode", {}).get("accepted_tokens_per_position")
    require(isinstance(values, dict), f"{row.get('case_id')}: missing positions")
    require(
        set(values) == EXPECTED_POSITIONS,
        f"{row.get('case_id')}: accepted-position schema drifted",
    )
    result = {}
    for position, value in values.items():
        require(
            isinstance(value, (int, float)) and not isinstance(value, bool),
            f"{row.get('case_id')}: non-numeric accepted-position value",
        )
        require(value >= 0, f"{row.get('case_id')}: negative accepted-position value")
        result[position] = float(value)
    return result


def analyze(payload: dict[str, Any]) -> dict[str, Any]:
    require(payload.get("schema") == "laguna-long-context-gate-v1", "schema drift")
    require(payload.get("status") == "PASS_ORACLE_EXACT", "run did not pass oracle")
    identity = payload.get("run_identity") or {}
    require(identity.get("run_role") == "candidate", "run role is not candidate")
    require(identity.get("oracle") is not None, "oracle was not requested")
    summary = payload.get("summary") or {}
    for name in (
        "intrinsic_pass_all",
        "oracle_exact_all",
        "cached_tokens_all_zero",
        "prompts_unique",
    ):
        require(summary.get(name) is True, f"summary gate failed: {name}")

    rows = payload.get("rows")
    require(isinstance(rows, list), "rows are missing")
    row_ids = tuple(row.get("case_id") for row in rows)
    require(row_ids == EXPECTED_ROW_IDS, f"row order/identity drifted: {row_ids}")

    manifest = payload.get("prompt_build_manifest")
    require(isinstance(manifest, list), "prompt build manifest is missing")
    require(
        tuple(row.get("case_id") for row in manifest) == EXPECTED_ROW_IDS,
        "prompt build manifest identity drifted",
    )

    by_id = {row["case_id"]: row for row in rows}
    long_evidence = []
    sentinel_evidence = []
    for row in rows:
        case_id = row["case_id"]
        require(row.get("passed") is True, f"{case_id}: intrinsic row gate failed")
        checks = row.get("checks") or {}
        require(
            checks and all(value is True for value in checks.values()),
            f"{case_id}: check drift",
        )
        oracle = row.get("oracle") or {}
        require(
            oracle.get("tested") is True
            and oracle.get("prompt_hash_equal") is True
            and oracle.get("token_ids_equal") is True
            and oracle.get("text_hash_equal") is True,
            f"{case_id}: oracle evidence failed",
        )
        require(row.get("cached_tokens") == 0, f"{case_id}: cache was not zero")

    for case_id in LONG_IDS:
        row = by_id[case_id]
        require(row.get("row_kind") == "long", f"{case_id}: not a long row")
        require(row.get("prompt_tokens") == 32640, f"{case_id}: prompt length drift")
        positions = position_counts(row)
        accepted = float(row["spec_decode"]["accepted_tokens"])
        require(sum(positions.values()) == accepted, f"{case_id}: position sum drift")
        beyond = sum(value for key, value in positions.items() if int(key) > 6)
        require(beyond == 0, f"{case_id}: accepted a token beyond position 6")
        require(
            row["spec_decode"].get("accepted_tokens_beyond_position_6") == 0,
            f"{case_id}: derived beyond-position counter drift",
        )
        max_position = row["spec_decode"].get("max_accepted_draft_position")
        require(
            max_position is None or max_position <= 6,
            f"{case_id}: max accepted position exceeds 6",
        )
        long_evidence.append(
            {
                "case_id": case_id,
                "accepted_tokens": accepted,
                "max_accepted_draft_position": max_position,
                "accepted_tokens_beyond_position_6": beyond,
            }
        )

    for case_id in SENTINEL_IDS:
        row = by_id[case_id]
        require(row.get("row_kind") == "sentinel", f"{case_id}: not a sentinel")
        require(row.get("prompt_tokens") == 256, f"{case_id}: prompt length drift")
        positions = position_counts(row)
        accepted = float(row["spec_decode"]["accepted_tokens"])
        require(sum(positions.values()) == accepted, f"{case_id}: position sum drift")
        beyond = sum(value for key, value in positions.items() if int(key) > 6)
        require(beyond > 0, f"{case_id}: did not prove deeper short acceptance")
        sentinel_evidence.append(
            {
                "case_id": case_id,
                "accepted_tokens": accepted,
                "accepted_tokens_beyond_position_6": beyond,
            }
        )

    warmup = by_id[WARMUP_ID]
    require(warmup.get("row_kind") == "long", "warmup row kind drifted")
    require(warmup.get("prompt_tokens") == 1024, "warmup prompt length drifted")
    return {
        "schema": "laguna-long-mixed-depth-feasibility-v1",
        "status": "PASS_IMPLEMENTATION_AUTHORIZED",
        "source_implementation_exists": False,
        "long_context_depth": 7,
        "target_verifier_width": 12,
        "long_rows": long_evidence,
        "sentinels": sentinel_evidence,
        "note": (
            "This analysis authorizes only a default-off long-context source "
            "prototype under the preregistered gate; it is not endpoint or "
            "performance evidence."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    result = analyze(json.loads(args.input.read_text(encoding="utf-8")))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
