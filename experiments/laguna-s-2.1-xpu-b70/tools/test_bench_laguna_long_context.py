#!/usr/bin/env python3
"""CPU-only metric-contract tests for the Laguna long-context gate."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench_laguna_long_context as bench


def test_labeled_metric_values_accepts_label_order_and_sparse_positions() -> None:
    name = bench.SPEC_ACCEPTED_PER_POS
    metrics = "\n".join(
        (
            f'{name}{{engine="0",model_name="laguna",position="0"}} 7.0',
            f'{name}{{position="7",engine="0",model_name="laguna"}} 2.0',
            'unrelated_metric{position="7"} 99.0',
        )
    )

    assert bench.labeled_metric_values(metrics, name, "position") == {
        0: 7.0,
        7: 2.0,
    }


def test_labeled_metric_values_rejects_duplicate_position() -> None:
    name = bench.SPEC_ACCEPTED_PER_POS
    metrics = "\n".join(
        (
            f'{name}{{engine="0",position="0"}} 7.0',
            f'{name}{{engine="1",position="0"}} 8.0',
        )
    )

    with pytest.raises(ValueError, match="duplicate"):
        bench.labeled_metric_values(metrics, name, "position")


def test_accepted_per_position_ignores_non_position_metrics() -> None:
    deltas = {
        bench.SPEC_ACCEPTED: 9.0,
        f"{bench.SPEC_ACCEPTED_PER_POS}[0]": 7.0,
        f"{bench.SPEC_ACCEPTED_PER_POS}[1]": 2.0,
    }

    assert bench.accepted_per_position(deltas) == {0: 7.0, 1: 2.0}


def test_metric_delta_rejects_position_schema_drift() -> None:
    with pytest.raises(ValueError, match="key set changed"):
        bench.metric_delta({"position[0]": 1.0}, {"position[1]": 1.0})
