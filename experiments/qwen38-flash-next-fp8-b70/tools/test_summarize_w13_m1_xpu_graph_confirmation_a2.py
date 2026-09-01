#!/usr/bin/env python3
"""CPU-only tests for the bounded W13 N32 A2 summarizer."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HERE = Path(__file__).resolve().parent
MODULE = load_module(
    "q38_w13_confirmation_a2",
    HERE / "summarize-w13-m1-xpu-graph-confirmation-a2.py",
)
BASE_TEST = load_module(
    "q38_w13_confirmation_a1_tests",
    HERE / "test_summarize_w13_m1_xpu_graph_confirmation.py",
)


class ConfirmationA2SummaryTests(unittest.TestCase):
    def write_matrix(self, root: Path, **kwargs) -> None:
        original_seeds = BASE_TEST.MODULE.SEEDS
        try:
            BASE_TEST.MODULE.SEEDS = MODULE.SEEDS
            BASE_TEST.ConfirmationSummaryTests().write_matrix(root, **kwargs)
        finally:
            BASE_TEST.MODULE.SEEDS = original_seeds

    def test_passes_exact_eight_cell_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_matrix(root)
            result = MODULE.summarize(root)
            self.assertEqual(result["status"], "pass")
            self.assertEqual(len(result["rows"]), 8)
            self.assertTrue(result["gates"]["all_8_cells_exact"])
            self.assertEqual(result["gates"]["positive_cells"], 8)
            self.assertFalse(result["raw_cross_rank_timings_pooled"])

    def test_requires_at_least_seven_positive_cells(self) -> None:
        def mutate(cell, arm, value):
            if arm == "candidate" and cell in {
                "l0-r0-s20260827",
                "l0-r1-s20260827",
            }:
                value["graph"]["event_median_us"] *= 1.12

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_matrix(root, mutate=mutate)
            result = MODULE.summarize(root)
            self.assertEqual(result["status"], "failed_closed")
            self.assertEqual(result["gates"]["positive_cells"], 6)
            self.assertFalse(result["gates"]["at_least_7_positive_cells"])

    def test_rejects_one_inexact_cell(self) -> None:
        def mutate(cell, arm, value):
            if cell == "l47-r3-s20260827" and arm == "candidate":
                value["correctness"]["matches_control_authority"] = False

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_matrix(root, mutate=mutate)
            result = MODULE.summarize(root)
            self.assertEqual(result["status"], "failed_closed")
            self.assertFalse(result["gates"]["all_8_cells_exact"])

    def test_rejects_control_drift_over_two_percent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_matrix(root, after_factor=1.03)
            result = MODULE.summarize(root)
            self.assertEqual(result["status"], "failed_closed")
            self.assertFalse(result["gates"]["all_control_drifts_within_two_percent"])


if __name__ == "__main__":
    unittest.main()
