#!/usr/bin/env python3
"""Tests for the sealed current-f01e TP2/MTP1 result validator."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[3]
VALIDATOR = REPO / "experiments/qwen38-27b-b70/scripts/validate-20260826-qwen38-official-f01e-autoround-tp2-mtp1-f16-eager-depth-expansion-r1-result.py"
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp1-f16-eager-depth-expansion-r1-result.json"


class ResultValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location("tp2_mtp1_result_validator", VALIDATOR)
        assert spec and spec.loader
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.result = json.loads(RESULT.read_text())

    def test_raw_result_passes(self) -> None:
        self.assertEqual(
            self.module.validate(),
            {"status": "pass", "raw_cells": 6, "new_site_cells": 6, "target_parity": "6/6", "acceptance": "6/6", "quality_cache_zero": "16/16", "x0": "missing"},
        )

    def test_profile_is_exactly_tp2_mtp1_eager_f16(self) -> None:
        config = self.result["config"]
        self.assertEqual((config["tp"], config["mtp"], config["graph_mode"], config["kv"]), (2, 1, "off", "f16"))
        self.assertEqual(config["num_speculative_tokens"], 1)
        self.assertTrue(config["enforce_eager"])

    def test_six_measured_points_include_low_2k_without_x0(self) -> None:
        self.assertEqual([point["x"] for point in self.result["points"]], [2048, 4096, 8192, 16384, 24576, 32768])
        self.assertEqual(self.result["points"][0]["decode_tok_s"], 11.882449351158243)
        self.assertNotIn(0, [point["x"] for point in self.result["points"]])

    def test_acceptance_and_same_topology_parity_are_complete(self) -> None:
        for point in self.result["points"]:
            self.assertGreater(point["drafted_tokens"], 0)
            self.assertGreater(point["accepted_tokens"], 0)
            self.assertLessEqual(point["accepted_tokens"], point["drafted_tokens"])
            self.assertEqual(point["same_topology_target_comparison"], "exact")

    def test_replacement_authority_is_denied(self) -> None:
        authority = self.result["authority"]
        self.assertFalse(authority["headline_or_protected_replacement"])
        self.assertFalse(authority["target_only_profile_replacement"])
        self.assertFalse(authority["older_tp2_graph_series_replacement"])
        self.assertEqual(authority["protected_decode_values_unchanged"], [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144])


if __name__ == "__main__":
    unittest.main()
