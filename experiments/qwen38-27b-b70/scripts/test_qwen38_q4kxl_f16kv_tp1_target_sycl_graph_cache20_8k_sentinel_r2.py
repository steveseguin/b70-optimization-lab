#!/usr/bin/env python3
"""Focused inert tests for the Q4_K_XL cache20 report-corrected packet."""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUNNER_PATH = HERE / "run-20260826-qwen38-q4kxl-f16kv-tp1-target-sycl-graph-cache20-8k-sentinel-r2.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("qwen38_q4kxl_graph_cache20_r2_tested", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = load_runner()
        cls.overlay = cls.runner.load_overlay()
        cls.manifest = cls.runner.load_manifest()

    def test_only_reporting_and_lifecycle_change(self):
        delta = self.overlay["reporting_delta"]
        self.assertEqual(delta["configured_candidate_cache_limit"], 20)
        self.assertEqual(delta["old_inherited_constant"], 8)
        self.assertFalse(delta["runtime_source_change"])
        self.assertFalse(delta["runtime_binary_change"])
        self.assertFalse(delta["model_change"])
        self.assertFalse(delta["workload_change"])

    def test_cache20_parser_accepts_passing_summary(self):
        text = (
            "[SYCL-GRAPH] summary device=0 requested=146 compatibility_rejected=0 "
            "device_unsupported=0 cache_entries=20 cache_limit=20 cache_hit=126 "
            "cache_miss=20 cache_full=0 direct_replay=126 recorded=20 "
            "created=20 updated=0 recreated=0 replayed=146"
        )
        evidence = self.runner.graph_evidence_cache20(text)
        self.assertEqual(evidence["cache_limit"], 20)
        self.assertEqual(evidence["cache_hit"], 126)
        self.assertEqual(evidence["summary_count"], 1)

    def test_cache8_and_multiple_summaries_fail(self):
        valid = (
            "[SYCL-GRAPH] summary device=0 requested=146 compatibility_rejected=0 "
            "device_unsupported=0 cache_entries=20 cache_limit=20 cache_hit=126 "
            "cache_miss=20 cache_full=0 direct_replay=126 recorded=20 "
            "created=20 updated=0 recreated=0 replayed=146"
        )
        with self.assertRaises(self.runner.GateError):
            self.runner.graph_evidence_cache20(valid.replace("cache_limit=20", "cache_limit=8"))
        with self.assertRaises(self.runner.GateError):
            self.runner.graph_evidence_cache20(valid + "\n" + valid)

    def test_narrow_authority_and_protected_values(self):
        frozen = self.manifest["frozen_interpretation"]
        self.assertEqual(frozen["site_cells_authorized"], 0)
        self.assertFalse(frozen["full_graph_curve_authorized"])
        self.assertTrue(frozen["full_curve_preregistration_authorized_only_on_pass"])
        self.assertEqual(
            frozen["protected_decode_values"],
            [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144],
        )

    def test_inert_default_and_wrong_ack(self):
        with tempfile.TemporaryDirectory() as directory:
            before = set(Path(directory).iterdir())
            result = subprocess.run([sys.executable, str(RUNNER_PATH)], cwd=directory, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(before, set(Path(directory).iterdir()))
            plan = json.loads(result.stdout)
            self.assertEqual(plan["runtime_changes"], 0)
            self.assertEqual(plan["report_parser_cache_limit"], 20)
        result = subprocess.run([sys.executable, str(RUNNER_PATH), "--execute", "--ack", "wrong"], text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exact --ack required", result.stderr)


if __name__ == "__main__":
    unittest.main()
