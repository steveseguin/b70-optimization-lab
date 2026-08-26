#!/usr/bin/env python3
"""Tests for the sealed current-f01e TP2/MTP4 structural quarantine."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[3]
VALIDATOR = REPO / "experiments/qwen38-27b-b70/scripts/validate-20260826-qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-8k-sentinel-r1-result.py"
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-8k-sentinel-r1-result.json"


class ResultValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location("tp2_mtp4_result_validator", VALIDATOR)
        assert spec and spec.loader
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.result = json.loads(RESULT.read_text())

    def test_raw_quarantine_passes(self) -> None:
        self.assertEqual(
            self.module.validate(),
            {"status": "pass", "structural_quarantine_cells": 1, "measured_speed_cells": 0, "tp": 2, "mtp": 4, "divergence_token": 99, "runner_rc": 39},
        )

    def test_profile_is_exactly_tp2_mtp4_eager_f16(self) -> None:
        config = self.result["config"]
        self.assertEqual((config["tp"], config["mtp"], config["graph_mode"], config["kv"]), (2, 4, "off", "f16"))
        self.assertEqual(config["num_speculative_tokens"], 4)
        self.assertTrue(config["enforce_eager"])

    def test_only_8k_is_structurally_classified(self) -> None:
        authority = self.result["authority"]
        self.assertEqual(authority["site_structural_quarantine_cells"], 1)
        self.assertEqual(authority["site_measured_speed_cells"], 0)
        self.assertTrue(authority["x0_remains_missing"])
        self.assertFalse(authority["other_depths_tp_mtp_graph_or_kv_inferred"])

    def test_diagnostic_speed_has_no_site_authority(self) -> None:
        point = self.result["diagnostic_point"]
        self.assertEqual(point["x"], 8192)
        self.assertEqual(point["conventional_99_interval_decode_tok_s"], 21.915468017099425)
        self.assertFalse(point["site_speed_publication"])
        self.assertFalse(point["headline_authority"])

    def test_target_failure_is_exactly_token_99(self) -> None:
        failure = self.result["target_failure"]
        self.assertFalse(failure["passed"])
        self.assertEqual(failure["first_divergence"], {"zero_based": 98, "one_based": 99, "candidate": 411, "target": 579})
        self.assertEqual((self.result["mechanism"]["accepted_tokens"], self.result["mechanism"]["drafted_tokens"]), (97, 124))

    def test_replacement_authority_is_denied(self) -> None:
        authority = self.result["authority"]
        self.assertFalse(authority["headline_graph_or_frontier_replacement"])
        self.assertFalse(authority["historical_or_protected_replacement"])
        self.assertEqual(authority["protected_decode_values_unchanged"], [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144])


if __name__ == "__main__":
    unittest.main()
