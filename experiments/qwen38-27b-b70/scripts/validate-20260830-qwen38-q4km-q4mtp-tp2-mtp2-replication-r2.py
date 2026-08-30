#!/usr/bin/env python3
"""Fail-closed validator for the Qwen3.8 TP2/MTP2 fresh-server replication."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def metric(payload: dict) -> float:
    return float(
        payload["summary"][
            "class_balanced_tok_s_1_100_intervals_after_ttft"
        ]["median"]
    )


def validate_arm(root: Path, expected_depth: int) -> tuple[dict, dict]:
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
    return performance, identity


def rows_by_id(payload: dict) -> dict[str, dict]:
    return {row["prompt_id"]: row for row in payload["rows"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prereg", required=True, type=Path)
    parser.add_argument("--screen-result", required=True, type=Path)
    parser.add_argument("--oracle-dir", required=True, type=Path)
    parser.add_argument("--first-candidate-dir", required=True, type=Path)
    parser.add_argument("--replication-dir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    failures: list[str] = []
    comparisons: list[dict] = []
    oracle_speed = first_speed = replication_speed = None
    try:
        prereg = load(args.prereg)
        prior = prereg["prior_evidence"]
        frozen_hashes = {
            "screen_result_sha256": sha256(args.screen_result),
            "oracle_performance_sha256": sha256(
                args.oracle_dir / "performance.json"
            ),
            "first_candidate_performance_sha256": sha256(
                args.first_candidate_dir / "performance.json"
            ),
        }
        for key, actual in frozen_hashes.items():
            if actual != prior[key]:
                failures.append(f"frozen prior evidence differs: {key}")

        oracle, oracle_identity = validate_arm(args.oracle_dir, 0)
        first, first_identity = validate_arm(args.first_candidate_dir, 2)
        replication, replication_identity = validate_arm(args.replication_dir, 2)

        for key in ("target", "server", "backend", "suite"):
            hashes = {
                identity["artifacts"][key]["sha256"]
                for identity in (
                    oracle_identity,
                    first_identity,
                    replication_identity,
                )
            }
            if len(hashes) != 1:
                failures.append(f"artifact identity differs: {key}")
        for key in ("target", "draft", "server", "backend", "suite"):
            artifact_key = "llama_server" if key == "server" else (
                "libggml_sycl" if key == "backend" else key
            )
            actual = replication_identity["artifacts"][key]["sha256"]
            if actual != prereg["identity"][f"{artifact_key}_sha256"]:
                failures.append(f"replication identity differs from prereg: {key}")
        if replication_identity["artifacts"]["prereg"]["sha256"] != sha256(
            args.prereg
        ):
            failures.append("replication prereg identity differs")
        if len(
            {
                oracle_identity["attempt"],
                first_identity["attempt"],
                replication_identity["attempt"],
            }
        ) != 3:
            failures.append("attempt identities are not distinct")

        oracle_rows = rows_by_id(oracle)
        first_rows = rows_by_id(first)
        replication_rows = rows_by_id(replication)
        if not (oracle_rows.keys() == first_rows.keys() == replication_rows.keys()):
            failures.append("prompt sets differ")
        for prompt_id in sorted(
            oracle_rows.keys() & first_rows.keys() & replication_rows.keys()
        ):
            oracle_row = oracle_rows[prompt_id]
            first_row = first_rows[prompt_id]
            replication_row = replication_rows[prompt_id]
            matches_oracle = (
                replication_row["token_ids"] == oracle_row["token_ids"]
            )
            matches_first = (
                replication_row["token_ids"] == first_row["token_ids"]
            )
            prompt_hashes_equal = len(
                {
                    oracle_row["prompt_sha256"],
                    first_row["prompt_sha256"],
                    replication_row["prompt_sha256"],
                }
            ) == 1
            if not matches_oracle:
                failures.append(f"replication token mismatch vs oracle: {prompt_id}")
            if not matches_first:
                failures.append(f"replication token mismatch vs R1: {prompt_id}")
            if not prompt_hashes_equal:
                failures.append(f"prompt hash mismatch: {prompt_id}")
            comparisons.append(
                {
                    "prompt_id": prompt_id,
                    "prompt_sha256_equal": prompt_hashes_equal,
                    "token_count": len(replication_row["token_ids"]),
                    "replication_equals_oracle": matches_oracle,
                    "replication_equals_first_candidate": matches_first,
                }
            )

        oracle_speed = metric(oracle)
        first_speed = metric(first)
        replication_speed = metric(replication)
        gain = (replication_speed / oracle_speed - 1.0) * 100.0
        rate_delta = abs(replication_speed / first_speed - 1.0) * 100.0
        if gain < float(prereg["pass_gate"]["minimum_gain_over_oracle_percent"]):
            failures.append("replication gain is below preregistered minimum")
        if rate_delta > float(
            prereg["pass_gate"][
                "maximum_absolute_rate_delta_from_first_candidate_percent"
            ]
        ):
            failures.append("replication rate delta exceeds preregistered maximum")
    except (AssertionError, KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
        failures.append(f"replication validation failed: {exc!r}")

    exact_oracle = sum(item["replication_equals_oracle"] for item in comparisons)
    exact_first = sum(
        item["replication_equals_first_candidate"] for item in comparisons
    )
    payload = {
        "schema": "neural.download.qwen38-q4km-q4mtp-tp2-mtp2-replication-result.v1",
        "created_utc": dt.datetime.now(dt.UTC).isoformat(),
        "status": "passed-replication" if not failures else "failed",
        "prereg_sha256": sha256(args.prereg),
        "oracle_dir": str(args.oracle_dir),
        "first_candidate_dir": str(args.first_candidate_dir),
        "replication_dir": str(args.replication_dir),
        "oracle_tok_s": oracle_speed,
        "first_candidate_tok_s": first_speed,
        "replication_tok_s": replication_speed,
        "replication_gain_percent": (
            (replication_speed / oracle_speed - 1.0) * 100.0
            if oracle_speed and replication_speed
            else None
        ),
        "replication_rate_delta_from_first_percent": (
            (replication_speed / first_speed - 1.0) * 100.0
            if first_speed and replication_speed
            else None
        ),
        "prompt_comparisons": comparisons,
        "exact_array_matches_vs_oracle": exact_oracle,
        "exact_array_matches_vs_first_candidate": exact_first,
        "required_exact_array_matches": 12,
        "failures": failures,
        "promotion_attestation_authorized": not failures,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
