#!/usr/bin/env python3
"""Regression tests for Qwen3.8 quality-suite baseline semantics."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "qwen38-text-quality-suite.py"
SPEC = importlib.util.spec_from_file_location("qwen38_quality_suite", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {SCRIPT}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BaselineStatusTest(unittest.TestCase):
    def test_absent_baseline_is_not_run_and_objective_only_can_pass(self) -> None:
        status, matched = MODULE.baseline_result({}, False)
        self.assertEqual(status, "not_run")
        self.assertIsNone(matched)
        self.assertEqual(MODULE.quality_exit_code(True, matched, False), 0)
        self.assertEqual(MODULE.quality_exit_code(True, matched, True), 1)

    def test_matching_baseline_passes(self) -> None:
        status, matched = MODULE.baseline_result(
            {"exact:code_execution:same_hash": True}, True
        )
        self.assertEqual(status, "passed")
        self.assertIs(matched, True)
        self.assertEqual(MODULE.quality_exit_code(True, matched, True), 0)

    def test_mismatch_and_empty_requested_baseline_fail(self) -> None:
        for comparisons in (
            {"exact:code_execution:same_hash": False},
            {},
        ):
            with self.subTest(comparisons=comparisons):
                status, matched = MODULE.baseline_result(comparisons, True)
                self.assertEqual(status, "failed")
                self.assertIs(matched, False)
                self.assertEqual(MODULE.quality_exit_code(True, matched, False), 1)

    def test_objective_failure_always_fails(self) -> None:
        self.assertEqual(MODULE.quality_exit_code(False, True, False), 1)


if __name__ == "__main__":
    unittest.main()
