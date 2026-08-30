#!/usr/bin/env python3
"""Qualify output-audited HTTP concurrency and summarize queued latency."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any


def percentile(values: list[Any], fraction: float) -> float | None:
    finite = sorted(
        float(value)
        for value in values
        if isinstance(value, (int, float)) and math.isfinite(value)
    )
    if not finite:
        return None
    position = (len(finite) - 1) * fraction
    low = int(position)
    high = min(low + 1, len(finite) - 1)
    weight = position - low
    return finite[low] * (1 - weight) + finite[high] * weight


def milliseconds(values: list[Any], fraction: float) -> float | None:
    value = percentile(values, fraction)
    return value * 1000 if value is not None else None


def qualify(
    result: dict[str, Any],
    *,
    pilot: bool,
    active_slots: int,
    expected_oracle_rows: int = 64,
    pilot_require_batch_gates: bool = False,
    pilot_from_batch: bool = False,
) -> dict[str, Any]:
    oracle = result["oracle"]["rows"]
    batches = result["batches"]
    batch_rows = [row for batch in batches for row in batch["rows"]]
    all_rows = oracle + batch_rows
    oracle_raw_complete = len(oracle) == expected_oracle_rows and all(
        row.get("completion_tokens") == 128
        and len(row.get("token_ids", [])) == 128
        for row in oracle
    )
    oracle_compact_complete = len(oracle) == expected_oracle_rows and all(
        row.get("completion_tokens") == 128
        and isinstance(row.get("token_ids_sha256"), str)
        and re.fullmatch(r"[0-9a-f]{64}", row["token_ids_sha256"])
        for row in oracle
    )
    batch_pilot_complete = (
        len(batches) == 1
        and len(batch_rows) == expected_oracle_rows
        and all(
            row.get("completion_tokens") == 128
            and len(row.get("token_ids", [])) == 128
            for row in batch_rows
        )
    )
    oracle_evidence_complete = (
        batch_pilot_complete
        if pilot_from_batch
        else (oracle_raw_complete if pilot else oracle_compact_complete)
    )
    counts_complete = all(row.get("completion_tokens") == 128 for row in all_rows)
    batch_ids_complete = all(
        len(row.get("token_ids", [])) == 128 for row in batch_rows
    )
    oracle_cache_zero = result["oracle"]["cached_tokens_all_zero"] is True
    cache_zero = oracle_cache_zero and all(
        batch["cached_tokens_all_zero"] for batch in batches
    )
    collisions = sum(
        batch.get("cross_base_oracle_collision_count", 0) for batch in batches
    )
    isolation = all(
        batch.get("complete_token_id_identity_all") for batch in batches
    ) and collisions == 0

    latency = []
    for batch in batches:
        ttft = [row.get("ttft_s") for row in batch["rows"]]
        elapsed = [row.get("elapsed_s") for row in batch["rows"]]
        latency.append(
            {
                "concurrent_users": batch["concurrency"],
                "aggregate_tok_s_wall": batch["aggregate_tok_s_wall"],
                "ttft_ms_p50": milliseconds(ttft, 0.50),
                "ttft_ms_p95": milliseconds(ttft, 0.95),
                "end_to_end_ms_p50": milliseconds(elapsed, 0.50),
                "end_to_end_ms_p95": milliseconds(elapsed, 0.95),
                "queued_profile": batch["concurrency"] > active_slots,
            }
        )

    batch_gates_passed = (
        counts_complete and batch_ids_complete and cache_zero and isolation
    )
    passed = oracle_evidence_complete and oracle_cache_zero and (
        (pilot and not pilot_require_batch_gates) or batch_gates_passed
    )
    return {
        "classification": (
            "qualified-oracle-pilot"
            if passed and pilot
            else (
                "output-isolation-qualified-shape-variant"
                if passed
                else "failed-closed"
            )
        ),
        "pilot": pilot,
        "pilot_require_batch_gates": pilot_require_batch_gates,
        "pilot_from_batch": pilot_from_batch,
        "batch_gates_passed": batch_gates_passed,
        "expected_oracle_rows": expected_oracle_rows,
        "oracle_rows_expected_complete": oracle_evidence_complete,
        # Retain the original field for old evidence consumers. It means
        # exactly what its name says and is deliberately false for p128.
        "oracle_rows_64_complete": len(oracle) == 64 and oracle_evidence_complete,
        "oracle_raw_token_ids_complete": oracle_raw_complete,
        "oracle_compact_digests_complete": oracle_compact_complete,
        "completion_tokens_128_all": counts_complete,
        "complete_token_id_identity_all": batch_ids_complete,
        "cached_tokens_all_zero": cache_zero,
        "cross_base_oracle_collision_count": collisions,
        "server_active_slots": active_slots,
        "queued_latency_boundary": (
            f"concurrency > {active_slots} includes service queueing"
        ),
        "latency": latency,
    }


def compact_oracle(result: dict[str, Any], *, from_batch: bool = False) -> dict[str, Any]:
    rows = result["batches"][0]["rows"] if from_batch else result["oracle"]["rows"]
    return {
        "schema": "neural.download.concurrency-token-oracle-digests.v1",
        "cached_tokens_zero": (
            result["batches"][0]["cached_tokens_all_zero"]
            if from_batch
            else result["oracle"]["cached_tokens_all_zero"]
        ),
        "rows": [
            {
                "base_prompt_id": re.sub(r"-c[0-9]+$", "", row["prompt_id"]),
                "prompt_id": row["prompt_id"],
                "prompt_sha256": row["prompt_sha256"],
                "completion_tokens": row["completion_tokens"],
                "token_ids_sha256": hashlib.sha256(
                    json.dumps(
                        row["token_ids"], separators=(",", ":")
                    ).encode()
                ).hexdigest(),
            }
            for row in rows
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--active-slots", type=int, required=True)
    parser.add_argument("--expected-oracle-rows", type=int, default=64)
    parser.add_argument("--pilot-require-batch-gates", action="store_true")
    parser.add_argument("--pilot-from-batch", action="store_true")
    parser.add_argument("--oracle-out", type=Path)
    args = parser.parse_args()
    if args.active_slots < 1:
        raise SystemExit("--active-slots must be positive")
    if args.expected_oracle_rows < 1:
        raise SystemExit("--expected-oracle-rows must be positive")
    if args.pilot != bool(args.oracle_out):
        raise SystemExit("pilot mode requires --oracle-out and publication mode forbids it")
    if args.pilot_require_batch_gates and not args.pilot:
        raise SystemExit("--pilot-require-batch-gates requires --pilot")
    if args.pilot_from_batch and not args.pilot:
        raise SystemExit("--pilot-from-batch requires --pilot")

    result = json.loads(args.result.read_text())
    qualification = qualify(
        result,
        pilot=args.pilot,
        active_slots=args.active_slots,
        expected_oracle_rows=args.expected_oracle_rows,
        pilot_require_batch_gates=args.pilot_require_batch_gates,
        pilot_from_batch=args.pilot_from_batch,
    )
    args.out.write_text(json.dumps(qualification, indent=2, sort_keys=True) + "\n")
    if args.pilot and qualification["classification"] == "qualified-oracle-pilot":
        assert args.oracle_out is not None
        args.oracle_out.write_text(
            json.dumps(
                compact_oracle(result, from_batch=args.pilot_from_batch),
                indent=2,
                sort_keys=True,
            ) + "\n"
        )
    return 0 if qualification["classification"] != "failed-closed" else 3


if __name__ == "__main__":
    raise SystemExit(main())
