#!/usr/bin/env python3
"""Tests for the current-f01e TP2/MTP0 PIECEWISE partial result."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[3]
VALIDATOR = REPO / "experiments/qwen38-27b-b70/scripts/validate-20260826-qwen38-official-f01e-autoround-tp2-mtp0-f16-piecewise-depth-r1-result.py"
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp0-f16-piecewise-depth-r1-result.json"


class ResultValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location("tp2_piecewise_result_validator", VALIDATOR)
        assert spec and spec.loader
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.result = json.loads(RESULT.read_text())

    def test_raw_partial_result_passes(self) -> None:
        self.assertEqual(self.module.validate(), {"status": "pass", "raw_exact": "6/6", "target_parity": "4/6", "new_site_measured": 4, "quarantined": [8192, 16384], "quality_cache_zero": "16/16", "graph_mode": "PIECEWISE", "x0": "missing"})

    def test_profile_is_exactly_tp2_target_only_piecewise_f16(self) -> None:
        config = self.result["config"]
        self.assertEqual((config["tp"], config["mtp"], config["graph_mode"], config["kv"]), (2, 0, "PIECEWISE", "f16"))
        self.assertEqual(config["graph_capture_sizes"], [1])
        self.assertFalse(config["enforce_eager"])

    def test_only_four_target_parity_points_are_publishable(self) -> None:
        self.assertEqual([point["x"] for point in self.result["valid_points"]], [2048, 4096, 24576, 32768])
        self.assertEqual([point["decode_tok_s"] for point in self.result["valid_points"]], [39.676315011384126, 46.64233045432341, 42.16719656056682, 41.13662863433114])
        self.assertTrue(all(point["same_image_target_comparison"] == "exact" for point in self.result["valid_points"]))

    def test_8k_and_16k_are_speedless_site_quarantines(self) -> None:
        points = self.result["quarantined_points"]
        self.assertEqual([point["x"] for point in points], [8192, 16384])
        self.assertEqual([point["decode_tok_s_diagnostic_only"] for point in points], [45.21462067141575, 43.99393016711806])
        self.assertEqual([(point["first_divergence_one_based"], point["candidate_token"], point["target_token"]) for point in points], [(99, 411, 579), (32, 13, 11)])
        self.assertTrue(all(point["site_action"] == "quarantine-no-speed" for point in points))

    def test_full_global_gates_are_recorded(self) -> None:
        quality = self.result["quality"]
        graph = self.result["graph_and_topology"]
        self.assertTrue(quality["objective_passed"] and quality["same_topology_baseline_passed"] and quality["cache_zero_all_16_quality_requests"])
        self.assertTrue(graph["startup_graph_identity_passed"] and graph["tp2_workers_verified"] and graph["fresh_ext4_cache"])

    def test_replacement_authority_is_denied(self) -> None:
        authority = self.result["authority"]
        self.assertFalse(authority["headline_or_protected_replacement"])
        self.assertFalse(authority["current_eager_profile_replacement"])
        self.assertFalse(authority["dated_fully_certified_graph_profile_replacement"])
        self.assertFalse(authority["diagnostic_quarantine_speeds_exposed_on_site"])
        self.assertEqual(authority["protected_decode_values_unchanged"], [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144])


if __name__ == "__main__":
    unittest.main()
