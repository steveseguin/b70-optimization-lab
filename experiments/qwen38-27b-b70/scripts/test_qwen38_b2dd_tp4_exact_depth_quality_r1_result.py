#!/usr/bin/env python3
"""Focused tests for compact TP4 exact-depth result authority and validation."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-b2dd9ce73d-tp4-exact-depth-quality-r1-result.json"
VALIDATOR = HERE / "validate-20260826-qwen38-b2dd9ce73d-tp4-exact-depth-quality-r1-result.py"
DEPTHS = [2048, 4096, 8192, 16384, 24576, 32768]


class CompactResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))

    def test_exactly_six_nonzero_grade_c_cells(self):
        curve = self.result["serving_curve"]
        self.assertEqual(curve["evidence_grade"], "C")
        self.assertEqual([cell["active_context_tokens"] for cell in curve["cells"]], DEPTHS)
        self.assertTrue(all(cell["cached_tokens"] == 0 for cell in curve["cells"]))
        self.assertTrue(all(cell["completion_tokens"] == 128 for cell in curve["cells"]))
        self.assertTrue(all(cell["timestamped_events"] == 100 for cell in curve["cells"]))
        self.assertTrue(all(cell["inter_token_intervals"] == 99 for cell in curve["cells"]))

    def test_authority_excludes_x0_capacity_parent_headline_and_lmx(self):
        authority = self.result["authority"]
        self.assertEqual(authority["authorized_cells"], 6)
        self.assertEqual(authority["selectors"]["active_context_tokens"], DEPTHS)
        for key in (
            "depth_zero_cells",
            "configured_capacity_cells",
            "short_suite_parent_cells",
            "quality_workload_cells",
            "other_tp_mtp_kv_graph_or_quantization_cells",
            "prefill_cells",
        ):
            self.assertEqual(authority[key], 0)
        self.assertFalse(authority["protected_or_headline_replacement"])
        self.assertFalse(authority["localmaxxing_submission"])
        boundary = self.result["scope_boundary"]
        for value in ("x0", "Capacity", "short-suite", "protected", "LocalMaxxing"):
            self.assertIn(value, boundary)

    def test_identity_is_tp4_zero_overlay_graph_profile(self):
        identity = self.result["identity"]
        config = identity["configuration"]
        runtime = identity["runtime"]
        self.assertEqual(config["gpu_affinity"], [0, 1, 2, 3])
        self.assertEqual((config["tp"], config["mtp"], config["target_kv"]), (4, 0, "float16"))
        self.assertEqual(config["graph_mode"], "FULL_AND_PIECEWISE")
        self.assertEqual(config["max_model_len"], 32896)
        self.assertEqual(runtime["source_overlay"], runtime["decision_overlay"])
        self.assertEqual(runtime["source_overlay"], "none")

    def test_quality_graph_and_cleanup_disclosures(self):
        quality = self.result["quality"]
        self.assertTrue(quality["pass_all"])
        self.assertEqual((quality["exact_cases"]["passed"], quality["repeat_stability"]["runs"]), (7, 8))
        self.assertEqual(quality["baseline_comparisons"]["passed"], 24)
        self.assertEqual(quality["cache_zero_requests"]["passed"], 16)
        self.assertTrue(self.result["validation"]["graph_capture_passed"])
        self.assertTrue(self.result["validation"]["post_cleanup_passed"])
        self.assertFalse(self.result["validation"]["historical_speed_replacement_allowed"])

    def test_offline_validator_passes(self):
        process = subprocess.run(
            [sys.executable, "-B", str(VALIDATOR)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(process.returncode, 0, process.stderr or process.stdout)
        self.assertIn("PASS: compact TP4 evidence", process.stdout)


if __name__ == "__main__":
    unittest.main()
