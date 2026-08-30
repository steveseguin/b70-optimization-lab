#!/usr/bin/env python3
"""Fail-closed comparison for the Qwen3.8 TP2 MTP0/MTP2 screen."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def metric(payload: dict) -> float:
    return float(
        payload["summary"][
            "class_balanced_tok_s_1_100_intervals_after_ttft"
        ]["median"]
    )


def validate_arm(root: Path, expected_depth: int) -> tuple[dict, dict, dict]:
    performance = load(root / "performance.json")
    canaries = load(root / "canaries.json")
    identity = load(root / "campaign-identity.json")
    contract = identity["contract"]
    gate = performance["realistic_final_gate"]
    fresh = performance["fresh_response_validity"]
    assert contract["tp"] == 2
    assert contract["mtp_depth"] == expected_depth
    assert contract["prompt_cache"] is False
    assert gate["passed"] is True
    assert gate["cached_tokens_all_zero"] is True
    assert fresh["valid"] is True
    assert canaries["pass_all"] is True
    assert len(performance["rows"]) == 12
    assert all(row["cached_tokens"] == 0 for row in performance["rows"])
    return performance, canaries, identity


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--oracle-dir", required=True, type=Path)
    parser.add_argument("--candidate-dir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    failures: list[str] = []
    try:
        oracle, _, oracle_identity = validate_arm(args.oracle_dir, 0)
        candidate, _, candidate_identity = validate_arm(args.candidate_dir, 2)
        for key in ("target", "server", "backend", "suite", "prereg"):
            if oracle_identity["artifacts"][key]["sha256"] != candidate_identity[
                "artifacts"
            ][key]["sha256"]:
                failures.append(f"artifact identity differs: {key}")

        oracle_rows = {row["prompt_id"]: row for row in oracle["rows"]}
        candidate_rows = {row["prompt_id"]: row for row in candidate["rows"]}
        if oracle_rows.keys() != candidate_rows.keys():
            failures.append("prompt sets differ")
        comparisons = []
        for prompt_id in sorted(oracle_rows.keys() & candidate_rows.keys()):
            left = oracle_rows[prompt_id]
            right = candidate_rows[prompt_id]
            exact = left["token_ids"] == right["token_ids"]
            if not exact:
                failures.append(f"token mismatch: {prompt_id}")
            comparisons.append(
                {
                    "prompt_id": prompt_id,
                    "prompt_sha256_equal": left["prompt_sha256"]
                    == right["prompt_sha256"],
                    "token_count_oracle": len(left["token_ids"]),
                    "token_count_candidate": len(right["token_ids"]),
                    "token_ids_exact": exact,
                }
            )
        oracle_speed = metric(oracle)
        candidate_speed = metric(candidate)
    except (AssertionError, KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
        failures.append(f"arm validation failed: {exc!r}")
        comparisons = []
        oracle_speed = None
        candidate_speed = None

    payload = {
        "schema": "neural.download.qwen38-q4km-q4mtp-tp2-mtp2-screen-result.v1",
        "created_utc": dt.datetime.now(dt.UTC).isoformat(),
        "status": "passed-diagnostic" if not failures else "failed",
        "oracle_dir": str(args.oracle_dir),
        "candidate_dir": str(args.candidate_dir),
        "oracle_tok_s": oracle_speed,
        "candidate_tok_s": candidate_speed,
        "gain_percent": (
            (candidate_speed / oracle_speed - 1.0) * 100.0
            if oracle_speed and candidate_speed
            else None
        ),
        "prompt_comparisons": comparisons,
        "exact_array_matches": sum(
            item["token_ids_exact"] for item in comparisons
        ),
        "required_exact_array_matches": 12,
        "failures": failures,
        "promotion_authorized": False,
        "replication_authorized": not failures,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
