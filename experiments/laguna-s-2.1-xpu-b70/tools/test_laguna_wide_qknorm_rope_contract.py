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
    NATIVE_OP,
    REQUIRED_ROWS,
    position_starts,
    projection_contribution,
)


TOOLS = Path(__file__).resolve().parent
AGGREGATOR = TOOLS / "aggregate_laguna_wide_qknorm_rope.py"


def _payload(rank: int, rows: int) -> dict[str, object]:
    cycle_saving_ms = 8.0 if rows == 8182 else 2.0 if rows == 8094 else 1.0
    return {
        "rank": rank,
        "rows": rows,
        "mode": "wide-prefill",
        "native_op": NATIVE_OP,
        "position_starts": list(position_starts(rows)),
        "passed": True,
        "exact": "64/64",
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
    mutation: tuple[int, int, str, object] | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    inputs = []
    for rank in range(4):
        for rows in REQUIRED_ROWS:
            payload = _payload(rank, rows)
            if mutation is not None and (rank, rows) == mutation[:2]:
                payload[mutation[2]] = mutation[3]
            path = tmp_path / f"rank{rank}-rows{rows}.json"
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


def test_aggregate_accepts_complete_incumbent_matrix(tmp_path: Path) -> None:
    result, output = _run_aggregate(tmp_path)

    assert result.returncode == 0, result.stderr
    assert output["passed"] is True
    assert output["required_native_op"] == NATIVE_OP
    assert output["required_rows"] == list(REQUIRED_ROWS)
    assert all(
        rank["incumbent_32640_projected_saving_ms"] == 26.0
        for rank in output["ranks"].values()
    )


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
    tmp_path: Path, field: str, value: object, failure: str
) -> None:
    result, output = _run_aggregate(tmp_path, (0, 8182, field, value))

    assert result.returncode != 0
    assert output["passed"] is False
    assert any(failure in message for message in output["failures"])
