#!/usr/bin/env python3
"""Tests for the current-f01e TP4/MTP0 PIECEWISE partial result."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[3]
VALIDATOR = REPO / "experiments/qwen38-27b-b70/scripts/validate-20260826-qwen38-official-f01e-autoround-tp4-mtp0-f16-piecewise-depth-r1-result.py"
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp4-mtp0-f16-piecewise-depth-r1-result.json"


class ResultValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location("tp4_piecewise_result_validator", VALIDATOR)
        assert spec and spec.loader
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.result = json.loads(RESULT.read_text())

    def test_raw_partial_result_passes(self) -> None:
        self.assertEqual(self.module.validate(), {"status": "pass", "raw_exact": "6/6", "target_parity": "5/6", "new_site_measured": 5, "quarantined": [8192], "quality_cache_zero": "16/16", "graph_mode": "PIECEWISE", "x0": "missing"})

    def test_profile_is_exactly_tp4_target_only_piecewise_f16(self) -> None:
        config = self.result["config"]
        self.assertEqual((config["tp"], config["mtp"], config["graph_mode"], config["kv"]), (4, 0, "PIECEWISE", "f16"))
        self.assertEqual(config["graph_capture_sizes"], [1])
        self.assertFalse(config["enforce_eager"])

    def test_only_five_target_parity_points_are_publishable(self) -> None:
        self.assertEqual([p["x"] for p in self.result["valid_points"]], [2048, 4096, 16384, 24576, 32768])
        self.assertEqual([p["decode_tok_s"] for p in self.result["valid_points"]], [51.06747790791104, 64.42037960929412, 62.78221708432737, 62.092862199068605, 60.50826347203049])
        self.assertTrue(all(p["same_image_target_comparison"] == "exact" for p in self.result["valid_points"]))

    def test_8k_is_a_speedless_site_quarantine(self) -> None:
        point = self.result["quarantined_points"][0]
        self.assertEqual((point["x"], point["decode_tok_s_diagnostic_only"]), (8192, 63.755137080322065))
        self.assertEqual((point["first_divergence_one_based"], point["candidate_token"], point["target_token"]), (99, 411, 579))
        self.assertEqual(point["site_action"], "quarantine-no-speed")

    def test_full_global_gates_are_recorded(self) -> None:
        quality = self.result["quality"]
        graph = self.result["graph_and_topology"]
        self.assertTrue(quality["objective_passed"] and quality["same_topology_baseline_passed"] and quality["cache_zero_all_16_quality_requests"])
        self.assertTrue(graph["startup_graph_identity_passed"] and graph["tp4_workers_verified"] and graph["fresh_ext4_cache"])

    def test_replacement_authority_is_denied(self) -> None:
        authority = self.result["authority"]
        self.assertFalse(authority["headline_or_protected_replacement"])
        self.assertFalse(authority["current_eager_profile_replacement"])
        self.assertFalse(authority["dated_fully_certified_graph_profile_replacement"])
        self.assertFalse(authority["diagnostic_quarantine_speeds_exposed_on_site"])
        self.assertEqual(authority["protected_decode_values_unchanged"], [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144])


if __name__ == "__main__":
    unittest.main()
