#!/usr/bin/env python3
"""CPU-only tests for the incumbent wide-prefill component contract."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from laguna_wide_qknorm_rope_contract import (
    CHUNK_MULTIPLICITY,
    DEFAULT_GEOMETRY,
    GEOMETRIES,
    LONG_ROWS,
    NATIVE_OP,
    REQUIRED_ROWS,
    WG4_NATIVE_OP,
    geometries_for_rows,
    native_op_for_geometry,
    position_starts,
    projection_contribution,
    required_matrix,
)


TOOLS = Path(__file__).resolve().parent
AGGREGATOR = TOOLS / "aggregate_laguna_wide_qknorm_rope.py"

# wg4 is given the larger saving so the aggregator has to pick it.
CYCLE_SAVING_MS = {
    ("wg2", 8182): 8.0,
    ("wg2", 8094): 2.0,
    ("wg4", 8182): 10.0,
    ("wg4", 8094): 2.5,
}


def _payload(rank: int, rows: int, geometry: str) -> dict[str, object]:
    cycle_saving_ms = CYCLE_SAVING_MS.get((geometry, rows), 1.0)
    return {
        "rank": rank,
        "rows": rows,
        "geometry": geometry,
        "mode": "wide-prefill",
        "native_op": native_op_for_geometry(geometry),
        "position_starts": list(position_starts(rows)),
        "passed": True,
        "exact": "64/64",
        # Output hashes are deliberately geometry-independent: repacking heads
        # into work-groups must not move a bit.
        "cases": {
            case: {"last_hashes": {"q": f"q-{rank}-{rows}-{case}", "k": f"k-{case}"}}
            for case in ("full", "sliding")
        },
        "weighted_48_layer_cycle": {
            "baseline_ms": 100.0,
            "candidate_ms": 100.0 - cycle_saving_ms,
            "saving_ms": cycle_saving_ms,
        },
        "incumbent_32640_projection_contribution": projection_contribution(
            rows, cycle_saving_ms
        ),
    }


def _run_aggregate(
    tmp_path: Path,
    mutation: tuple[int, int, str, str, object] | None = None,
    extra: list[dict[str, object]] | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    inputs = []
    for rank in range(4):
        for rows in REQUIRED_ROWS:
            for geometry in geometries_for_rows(rows):
                payload = _payload(rank, rows, geometry)
                if mutation is not None and (rank, rows, geometry) == mutation[:3]:
                    payload[mutation[3]] = mutation[4]
                path = tmp_path / f"rank{rank}-rows{rows}-{geometry}.json"
                path.write_text(json.dumps(payload) + "\n")
                inputs.append(path)
    for index, payload in enumerate(extra or []):
        path = tmp_path / f"extra{index}.json"
        path.write_text(json.dumps(payload) + "\n")
        inputs.append(path)
    output = tmp_path / "aggregate.json"
    result = subprocess.run(
        [sys.executable, str(AGGREGATOR), *map(str, inputs), "--out", str(output)],
        check=False,
        capture_output=True,
        text=True,
    )
    return result, json.loads(output.read_text())


def test_incumbent_contract_matches_real_32640_partition() -> None:
    assert REQUIRED_ROWS == (1024, 4096, 8094, 8182)
    assert CHUNK_MULTIPLICITY == {1024: 0, 4096: 0, 8094: 1, 8182: 3}
    assert position_starts(8182) == (0, 8182, 16364)
    assert position_starts(8094) == (0, 8182, 16364, 24546)
    with pytest.raises(ValueError, match="rows must be one of"):
        position_starts(8192)


def test_only_long_rows_are_measured_in_both_geometries() -> None:
    assert GEOMETRIES == ("wg2", "wg4")
    assert DEFAULT_GEOMETRY == "wg2"
    assert LONG_ROWS == (8094, 8182)
    for rows in LONG_ROWS:
        assert geometries_for_rows(rows) == GEOMETRIES
    for rows in (1024, 4096):
        assert geometries_for_rows(rows) == (DEFAULT_GEOMETRY,)
    assert native_op_for_geometry("wg2") == NATIVE_OP
    assert native_op_for_geometry("wg4") == WG4_NATIVE_OP
    # Four ranks x four rows, plus the two long rows again at wg4.
    assert len(required_matrix(range(4))) == 24


def test_aggregate_accepts_complete_incumbent_matrix(tmp_path: Path) -> None:
    result, output = _run_aggregate(tmp_path)

    assert result.returncode == 0, result.stderr
    assert output["passed"] is True
    assert output["required_native_ops"] == {
        "wg2": NATIVE_OP,
        "wg4": WG4_NATIVE_OP,
    }
    assert output["required_rows"] == list(REQUIRED_ROWS)
    assert output["required_runs"] == 24
    for rank in output["ranks"].values():
        assert rank["incumbent_32640_projected_saving_ms_by_geometry"] == {
            "wg2": 26.0,
            "wg4": 32.5,
        }
        assert rank["best_geometry"] == "wg4"
        assert rank["incumbent_32640_projected_saving_ms"] == 32.5


def test_aggregate_rejects_geometries_that_disagree_bitwise(tmp_path: Path) -> None:
    drifted = {
        "full": {"last_hashes": {"q": "different", "k": "different"}},
        "sliding": {"last_hashes": {"q": "q-0-8182-sliding", "k": "k-sliding"}},
    }
    result, output = _run_aggregate(tmp_path, (0, 8182, "wg4", "cases", drifted))

    assert result.returncode != 0
    assert output["passed"] is False
    assert any(
        "geometries disagree bit-for-bit" in message for message in output["failures"]
    )


def test_aggregate_rejects_a_geometry_outside_the_matrix(tmp_path: Path) -> None:
    stray = _payload(0, 1024, "wg2")
    stray["geometry"] = "wg4"
    stray["native_op"] = WG4_NATIVE_OP
    result, output = _run_aggregate(tmp_path, extra=[stray])

    assert result.returncode != 0
    assert output["passed"] is False
    assert any("unexpected" in message for message in output["failures"])


@pytest.mark.parametrize("geometry", GEOMETRIES)
@pytest.mark.parametrize(
    ("field", "value", "failure"),
    [
        (
            "native_op",
            "laguna_wide_prefill_qk_norm_rope_out",
            "native op is not",
        ),
        ("position_starts", [0, 8192], "position starts are not"),
        (
            "incumbent_32640_projection_contribution",
            {"chunk_multiplicity": 1, "saving_ms": 8.0},
            "chunk multiplicity is not",
        ),
    ],
)
def test_aggregate_rejects_contract_drift(
    tmp_path: Path, geometry: str, field: str, value: object, failure: str
) -> None:
    result, output = _run_aggregate(tmp_path, (0, 8182, geometry, field, value))

    assert result.returncode != 0
    assert output["passed"] is False
    assert any(failure in message for message in output["failures"])
