#!/usr/bin/env python3
"""Tests for the bounded Flash-Next official-mode quality gate."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("qwen38-official-thinking-quality.py")
SPEC = importlib.util.spec_from_file_location("qwen38_official_quality", SCRIPT)
assert SPEC and SPEC.loader
quality = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(quality)


class OfficialThinkingQualityTests(unittest.TestCase):
    def test_official_sampling_is_frozen(self) -> None:
        self.assertEqual(
            quality.OFFICIAL_SAMPLING,
            {
                "temperature": 1.0,
                "top_p": 0.95,
                "top_k": 20,
                "min_p": 0.0,
                "presence_penalty": 0.0,
                "repetition_penalty": 1.0,
            },
        )

    def test_logic_is_casefolded_but_code_is_exact(self) -> None:
        cases = {case["name"]: case for case in quality.cases()}
        self.assertTrue(quality.answer_pass(cases["logic"], "Yes")[0])
        self.assertTrue(quality.answer_pass(cases["code_execution"], "14")[0])
        self.assertFalse(quality.answer_pass(cases["code_execution"], "30")[0])

    def test_json_fields_are_typed_by_value(self) -> None:
        case = next(case for case in quality.cases() if case["name"] == "json_schema")
        self.assertTrue(
            quality.answer_pass(case, '{"answer":42,"unit":"widgets"}')[0]
        )
        self.assertFalse(quality.answer_pass(case, '{"answer":41,"unit":"widgets"}')[0])

    def test_grid_runs_every_case_at_each_frozen_seed(self) -> None:
        schedule = quality.grid_schedule()
        self.assertEqual(len(schedule), 21)
        for case in quality.cases():
            self.assertEqual(
                [seed for seed, row in schedule if row["name"] == case["name"]],
                quality.GRID_SEEDS,
            )


if __name__ == "__main__":
    unittest.main()
