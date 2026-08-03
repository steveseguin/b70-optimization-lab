#!/usr/bin/env python3
"""Aggregate the four-rank Laguna wide-prefill component gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from laguna_wide_qknorm_rope_contract import (
    CHUNK_MULTIPLICITY,
    NATIVE_OP,
    REQUIRED_ROWS,
    position_starts,
)

REQUIRED_RANKS = range(4)
MIN_PROJECTED_SAVING_MS = 25.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    failures: list[str] = []
    runs: dict[tuple[int, int], dict[str, object]] = {}
    for path in args.inputs:
        payload = json.loads(path.read_text())
        identity = (payload.get("rank"), payload.get("rows"))
        if payload.get("mode") != "wide-prefill":
            failures.append(f"{path}: mode is not wide-prefill")
            continue
        if payload.get("native_op") != NATIVE_OP:
            failures.append(f"{path}: native op is not {NATIVE_OP}")
            continue
        if identity in runs:
            failures.append(f"{path}: duplicate rank/rows identity {identity}")
            continue
        payload["source_path"] = str(path.resolve())
        runs[identity] = payload

    required = {(rank, rows) for rank in REQUIRED_RANKS for rows in REQUIRED_ROWS}
    missing = sorted(required - runs.keys())
    unexpected = sorted(runs.keys() - required)
    if missing:
        failures.append(f"missing rank/rows runs: {missing}")
    if unexpected:
        failures.append(f"unexpected rank/rows runs: {unexpected}")

    ranks: dict[str, object] = {}
    for rank in REQUIRED_RANKS:
        rank_runs = {
            rows: runs[(rank, rows)] for rows in REQUIRED_ROWS if (rank, rows) in runs
        }
        failed_rows = [rows for rows, row in rank_runs.items() if not row["passed"]]
        if failed_rows:
            failures.append(f"rank {rank} failed rows: {failed_rows}")
        for rows, row in rank_runs.items():
            expected_starts = list(position_starts(rows))
            if row.get("position_starts") != expected_starts:
                failures.append(
                    f"rank {rank} rows {rows} position starts are not "
                    f"{expected_starts}"
                )
            projection = row.get("incumbent_32640_projection_contribution")
            if not isinstance(projection, dict):
                failures.append(f"rank {rank} rows {rows} projection is missing")
            elif projection.get("chunk_multiplicity") != CHUNK_MULTIPLICITY[rows]:
                failures.append(
                    f"rank {rank} rows {rows} chunk multiplicity is not "
                    f"{CHUNK_MULTIPLICITY[rows]}"
                )
        projected_saving_ms = sum(
            row.get("incumbent_32640_projection_contribution", {}).get(
                "saving_ms", 0.0
            )
            for row in rank_runs.values()
        )
        if len(rank_runs) == len(REQUIRED_ROWS) and (
            projected_saving_ms < MIN_PROJECTED_SAVING_MS
        ):
            failures.append(
                f"rank {rank} projected saving {projected_saving_ms:.6f} ms "
                f"is below {MIN_PROJECTED_SAVING_MS:.1f} ms"
            )
        ranks[str(rank)] = {
            "rows": {
                str(rows): {
                    "passed": row["passed"],
                    "exact": row["exact"],
                    "source_path": row["source_path"],
                    "weighted_48_layer_cycle": row["weighted_48_layer_cycle"],
                }
                for rows, row in rank_runs.items()
            },
            "incumbent_32640_projected_saving_ms": projected_saving_ms,
        }

    output = {
        "passed": not failures,
        "required_ranks": list(REQUIRED_RANKS),
        "required_rows": list(REQUIRED_ROWS),
        "required_native_op": NATIVE_OP,
        "incumbent_schedule": "8182 + 8182 + 8182 + 8094 = 32640",
        "minimum_projected_saving_ms_per_rank": MIN_PROJECTED_SAVING_MS,
        "failures": failures,
        "ranks": ranks,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output, indent=2))
    if failures:
        raise AssertionError(f"Laguna wide-prefill aggregate gate failed: {failures}")


if __name__ == "__main__":
    main()
