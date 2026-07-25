#!/usr/bin/env python3
"""CPU-only tests for the Laguna routed-W1 N32 aggregate gate."""

from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("analyze_laguna_w1_n32_gate.py")
SPEC = importlib.util.spec_from_file_location("n32_analyzer", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def make_cards(relative: float = 0.025) -> list[dict[str, object]]:
    return [
        {
            "rank": rank,
            "passed": True,
            "extension_sha256": "extension",
            "grouped_gemm_sha256": "grouped",
            "timing_fixture_sha256": "fixture",
            "physical_uuid": f"uuid-{rank}",
            "physical_bdf": f"bdf-{rank}",
            "relative_median_improvement": relative,
        }
        for rank in range(4)
    ]


def test_aggregate_accepts_four_card_two_percent_win():
    result = MODULE.aggregate_cards(make_cards())
    assert result["passed"] is True
    assert result["mean_relative_improvement"] == 0.025


def test_aggregate_rejects_sub_two_percent_mean():
    result = MODULE.aggregate_cards(make_cards(0.019))
    assert result["passed"] is False
    assert result["aggregate_checks"]["cross_card_relative_improvement"] is False


def test_aggregate_rejects_duplicate_physical_card():
    cards = make_cards()
    cards[3]["physical_uuid"] = cards[2]["physical_uuid"]
    result = MODULE.aggregate_cards(cards)
    assert result["passed"] is False
    assert result["aggregate_checks"]["four_distinct_physical_uuids"] is False
