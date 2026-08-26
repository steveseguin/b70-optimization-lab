#!/usr/bin/env python3
"""Tests for the sealed current-f01e TP2/MTP3 result validator."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[3]
VALIDATOR = REPO / "experiments/qwen38-27b-b70/scripts/validate-20260826-qwen38-official-f01e-autoround-tp2-mtp3-f16-eager-depth-expansion-r1-result.py"
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp3-f16-eager-depth-expansion-r1-result.json"


class ResultValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location("tp2_mtp3_result_validator", VALIDATOR)
        assert spec and spec.loader
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.result = json.loads(RESULT.read_text())

    def test_raw_result_passes(self) -> None:
        self.assertEqual(
            self.module.validate(),
            {"status": "pass", "raw_exact": "5/5", "acceptance": "5/5", "target_parity": "5/5", "new_site_measured": 5, "structurally_excluded": [2048], "quality_cache_zero": "16/16", "x0": "missing"},
        )

    def test_profile_is_exactly_tp2_mtp3_eager_f16(self) -> None:
        config = self.result["config"]
        self.assertEqual((config["tp"], config["mtp"], config["graph_mode"], config["kv"]), (2, 3, "off", "f16"))
        self.assertEqual(config["num_speculative_tokens"], 3)
        self.assertTrue(config["enforce_eager"])

    def test_only_five_observed_target_parity_points_are_publishable(self) -> None:
        self.assertEqual([point["x"] for point in self.result["valid_points"]], [4096, 8192, 16384, 24576, 32768])
        self.assertNotIn(2048, [point["x"] for point in self.result["valid_points"]])
        self.assertNotIn(0, [point["x"] for point in self.result["valid_points"]])
        self.assertTrue(all(point["same_topology_target_comparison"] == "exact" for point in self.result["valid_points"]))

    def test_2k_is_parent_quarantined_without_an_mtp3_speed(self) -> None:
        point = self.result["structurally_excluded_points"][0]
        self.assertEqual(point["x"], 2048)
        self.assertEqual(point["state"], "quarantined-by-parent-oracle")
        self.assertEqual(point["parent_first_divergence_one_based"], 90)
        self.assertFalse(point["speed_observed"])
        self.assertNotIn("decode_tok_s", point)
        self.assertEqual(point["site_action"], "quarantine-no-speed")

    def test_replacement_authority_is_denied(self) -> None:
        authority = self.result["authority"]
        self.assertFalse(authority["headline_or_protected_replacement"])
        self.assertFalse(authority["target_only_profile_replacement"])
        self.assertFalse(authority["mtp1_profile_replacement"])
        self.assertFalse(authority["mtp2_profile_replacement"])
        self.assertFalse(authority["older_tp2_graph_series_replacement"])
        self.assertEqual(authority["protected_decode_values_unchanged"], [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144])


if __name__ == "__main__":
    unittest.main()
