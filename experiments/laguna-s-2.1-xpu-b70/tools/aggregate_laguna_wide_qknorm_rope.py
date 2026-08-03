#!/usr/bin/env python3
"""Aggregate the four-rank Laguna wide-prefill component gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from laguna_wide_qknorm_rope_contract import (
    CHUNK_MULTIPLICITY,
    DEFAULT_GEOMETRY,
    GEOMETRIES,
    LONG_ROWS,
    REQUIRED_ROWS,
    geometries_for_rows,
    native_op_for_geometry,
    position_starts,
    required_matrix,
)

REQUIRED_RANKS = range(4)
MIN_PROJECTED_SAVING_MS = 25.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    failures: list[str] = []
    runs: dict[tuple[int, int, str], dict[str, object]] = {}
    for path in args.inputs:
        payload = json.loads(path.read_text())
        geometry = payload.get("geometry", DEFAULT_GEOMETRY)
        identity = (payload.get("rank"), payload.get("rows"), geometry)
        if payload.get("mode") != "wide-prefill":
            failures.append(f"{path}: mode is not wide-prefill")
            continue
        if geometry not in GEOMETRIES:
            failures.append(f"{path}: geometry {geometry!r} is not registered")
            continue
        expected_op = native_op_for_geometry(geometry)
        if payload.get("native_op") != expected_op:
            failures.append(f"{path}: native op is not {expected_op}")
            continue
        if identity in runs:
            failures.append(
                f"{path}: duplicate rank/rows/geometry identity {identity}"
            )
            continue
        payload["source_path"] = str(path.resolve())
        runs[identity] = payload

    required = required_matrix(REQUIRED_RANKS)
    missing = sorted(required - runs.keys())
    unexpected = sorted(runs.keys() - required)
    if missing:
        failures.append(f"missing rank/rows/geometry runs: {missing}")
    if unexpected:
        failures.append(f"unexpected rank/rows/geometry runs: {unexpected}")

    ranks: dict[str, object] = {}
    for rank in REQUIRED_RANKS:
        rank_runs = {
            (rows, geometry): runs[(rank, rows, geometry)]
            for rows in REQUIRED_ROWS
            for geometry in geometries_for_rows(rows)
            if (rank, rows, geometry) in runs
        }
        failed = [key for key, row in rank_runs.items() if not row["passed"]]
        if failed:
            failures.append(f"rank {rank} failed rows/geometries: {failed}")
        for (rows, geometry), row in rank_runs.items():
            expected_starts = list(position_starts(rows))
            if row.get("position_starts") != expected_starts:
                failures.append(
                    f"rank {rank} rows {rows} {geometry} position starts are "
                    f"not {expected_starts}"
                )
            projection = row.get("incumbent_32640_projection_contribution")
            if not isinstance(projection, dict):
                failures.append(
                    f"rank {rank} rows {rows} {geometry} projection is missing"
                )
            elif projection.get("chunk_multiplicity") != CHUNK_MULTIPLICITY[rows]:
                failures.append(
                    f"rank {rank} rows {rows} {geometry} chunk multiplicity is "
                    f"not {CHUNK_MULTIPLICITY[rows]}"
                )

        # Repacking heads into work-groups must not move a single bit. The gate
        # drives both geometries from the same seeds and positions, so their
        # recorded output hashes have to match exactly. A mismatch means the
        # reduction is not head-independent and neither geometry is promotable.
        for rows in LONG_ROWS:
            present = [g for g in GEOMETRIES if (rows, g) in rank_runs]
            if len(present) != len(GEOMETRIES):
                continue
            for case in rank_runs[(rows, GEOMETRIES[0])].get("cases", {}):
                hashes = {
                    g: rank_runs[(rows, g)].get("cases", {}).get(case, {}).get(
                        "last_hashes"
                    )
                    for g in GEOMETRIES
                }
                distinct = {
                    json.dumps(value, sort_keys=True) for value in hashes.values()
                }
                if len(distinct) != 1:
                    failures.append(
                        f"rank {rank} rows {rows} case {case} geometries "
                        f"disagree bit-for-bit: {hashes}"
                    )

        # Score each geometry over a full row set: the long rows at that
        # geometry, the short rows at the single geometry they are measured in.
        geometry_savings: dict[str, float] = {}
        for geometry in GEOMETRIES:
            covered = []
            for rows in REQUIRED_ROWS:
                measured = geometries_for_rows(rows)
                key = (rows, geometry if geometry in measured else DEFAULT_GEOMETRY)
                if key in rank_runs:
                    covered.append(rank_runs[key])
            if len(covered) != len(REQUIRED_ROWS):
                continue
            geometry_savings[geometry] = sum(
                row.get("incumbent_32640_projection_contribution", {}).get(
                    "saving_ms", 0.0
                )
                for row in covered
            )

        best_geometry = None
        best_saving = 0.0
        if geometry_savings:
            best_geometry = max(geometry_savings, key=geometry_savings.__getitem__)
            best_saving = geometry_savings[best_geometry]
            if best_saving < MIN_PROJECTED_SAVING_MS:
                failures.append(
                    f"rank {rank} best projected saving {best_saving:.6f} ms "
                    f"({best_geometry}) is below {MIN_PROJECTED_SAVING_MS:.1f} ms"
                )

        ranks[str(rank)] = {
            "rows": {
                f"{rows}:{geometry}": {
                    "passed": row["passed"],
                    "exact": row["exact"],
                    "geometry": geometry,
                    "source_path": row["source_path"],
                    "weighted_48_layer_cycle": row["weighted_48_layer_cycle"],
                }
                for (rows, geometry), row in rank_runs.items()
            },
            "incumbent_32640_projected_saving_ms_by_geometry": geometry_savings,
            "best_geometry": best_geometry,
            "incumbent_32640_projected_saving_ms": best_saving,
        }

    output = {
        "passed": not failures,
        "required_ranks": list(REQUIRED_RANKS),
        "required_rows": list(REQUIRED_ROWS),
        "required_geometries": list(GEOMETRIES),
        "required_native_ops": {
            geometry: native_op_for_geometry(geometry) for geometry in GEOMETRIES
        },
        "required_runs": len(required),
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
