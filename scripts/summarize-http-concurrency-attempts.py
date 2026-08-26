#!/usr/bin/env python3
"""Qualify and aggregate fresh-server HTTP concurrency attempts."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import statistics
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-relative-range-percent", type=float, default=10.0)
    parser.add_argument("--max-latency-relative-range-percent", type=float, default=15.0)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    if len(args.attempt) < 2:
        raise SystemExit("at least two --attempt directories are required")
    if args.out.exists():
        raise SystemExit(f"refusing to overwrite {args.out}")

    attempts: list[dict[str, Any]] = []
    expected_concurrency: list[int] | None = None
    oracle_hash: str | None = None
    for root in args.attempt:
        result_path = root / "result.json"
        qualification_path = root / "qualification.json"
        if not result_path.is_file() or not qualification_path.is_file():
            raise SystemExit(f"missing result/qualification under {root}")
        result = json.loads(result_path.read_text())
        qualification = json.loads(qualification_path.read_text())
        checks = {
            "classification": qualification.get("classification")
            in {"output-identity-qualified", "output-isolation-qualified-shape-variant"},
            "completion_tokens_128_all": qualification.get("completion_tokens_128_all") is True,
            "cached_tokens_all_zero": qualification.get("cached_tokens_all_zero") is True,
            "complete_token_id_identity_all": qualification.get("complete_token_id_identity_all") is True,
            "cross_base_oracle_collision_count_zero": qualification.get("cross_base_oracle_collision_count") == 0,
        }
        if not all(checks.values()):
            raise SystemExit(f"qualification failed for {root}: {checks}")
        batches = result.get("batches", [])
        concurrency = [row["concurrency"] for row in batches]
        if concurrency != sorted(set(concurrency)):
            raise SystemExit(f"invalid concurrency order under {root}: {concurrency}")
        if expected_concurrency is None:
            expected_concurrency = concurrency
        elif concurrency != expected_concurrency:
            raise SystemExit("attempt concurrency sets differ")
        this_oracle = result["config"].get("oracle_digests_sha256")
        if not isinstance(this_oracle, str):
            raise SystemExit(f"missing frozen oracle hash under {root}")
        if oracle_hash is None:
            oracle_hash = this_oracle
        elif this_oracle != oracle_hash:
            raise SystemExit("attempt oracle hashes differ")
        latency_rows = qualification.get("latency")
        if not isinstance(latency_rows, list):
            raise SystemExit(f"missing latency rows under {root}")
        latency_by_concurrency = {
            row.get("concurrent_users"): row for row in latency_rows
            if isinstance(row, dict)
        }
        if sorted(latency_by_concurrency) != expected_concurrency:
            raise SystemExit(f"latency concurrency set differs under {root}")
        attempts.append({
            "root": str(root),
            "result_sha256": sha256(result_path),
            "qualification_sha256": sha256(qualification_path),
            "checks": checks,
            "rates": {row["concurrency"]: row["aggregate_tok_s_wall"] for row in batches},
            "oracle_exact": {
                row["concurrency"]: f"{row['oracle_exact_count']}/{row['oracle_exact_total']}"
                for row in batches
            },
            "latency": latency_by_concurrency,
        })

    assert expected_concurrency is not None
    points = []
    for concurrency in expected_concurrency:
        values = [attempt["rates"][concurrency] for attempt in attempts]
        median = statistics.median(values)
        relative_range = ((max(values) - min(values)) / median * 100.0) if median else None
        latency_metrics = {}
        for metric in (
            "ttft_ms_p50", "ttft_ms_p95",
            "end_to_end_ms_p50", "end_to_end_ms_p95",
        ):
            latency_values = [
                attempt["latency"][concurrency].get(metric)
                for attempt in attempts
            ]
            if not all(isinstance(value, (int, float)) for value in latency_values):
                raise SystemExit(f"missing {metric} at concurrency {concurrency}")
            latency_median = statistics.median(latency_values)
            latency_range = (
                (max(latency_values) - min(latency_values)) / latency_median * 100.0
                if latency_median else None
            )
            latency_metrics[metric] = {
                "attempt_values": latency_values,
                "median": latency_median,
                "relative_range_percent": latency_range,
                "stability_passed": latency_range is not None
                and latency_range <= args.max_latency_relative_range_percent,
            }
        queued_flags = [
            attempt["latency"][concurrency].get("queued_profile")
            for attempt in attempts
        ]
        if len(set(queued_flags)) != 1 or not all(isinstance(v, bool) for v in queued_flags):
            raise SystemExit(f"queued-profile boundary differs at concurrency {concurrency}")
        points.append({
            "concurrent_users": concurrency,
            "attempt_values_tok_s": values,
            "median_aggregate_tok_s": median,
            "median_per_user_tok_s": median / concurrency,
            "relative_range_percent": relative_range,
            "stability_passed": relative_range is not None
            and relative_range <= args.max_relative_range_percent,
            "queued_profile": queued_flags[0],
            "latency_ms": latency_metrics,
        })
    passed = all(
        point["stability_passed"]
        and all(metric["stability_passed"] for metric in point["latency_ms"].values())
        for point in points
    )
    out = {
        "schema": "neural.download.http-concurrency-aggregate.v1",
        "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
        "label": args.label,
        "classification": "qualified-output-audited-http-concurrency" if passed else "failed-stability-gate",
        "fresh_server_attempts": len(attempts),
        "oracle_digests_sha256": oracle_hash,
        "max_relative_range_percent": args.max_relative_range_percent,
        "max_latency_relative_range_percent": args.max_latency_relative_range_percent,
        "attempts": attempts,
        "points": points,
        "reporting_boundary": "Every throughput and latency value is the median of exact fresh-server attempts. No interpolation or extrapolation. Sequential identity is reported separately from output isolation; queued_profile=true includes service queueing.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "classification": out["classification"],
        "output": str(args.out),
        "points": points,
    }, indent=2))
    return 0 if passed else 3


if __name__ == "__main__":
    raise SystemExit(main())
