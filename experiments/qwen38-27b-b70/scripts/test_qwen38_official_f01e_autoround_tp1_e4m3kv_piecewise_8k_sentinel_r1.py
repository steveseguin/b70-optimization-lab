#!/usr/bin/env python3
"""Inert contract tests for the f01e AutoRound E4M3 PIECEWISE sentinel."""

from __future__ import annotations

import json
import pathlib
import unittest


REPO = pathlib.Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-26-qwen38-official-f01e-autoround-tp1-e4m3kv-piecewise-8k-sentinel-r1-prereg.json"
RUNNER = LANE / "scripts/run-20260826-qwen38-official-f01e-autoround-tp1-e4m3kv-piecewise-8k-sentinel-r1.sh"


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.runner = RUNNER.read_text(encoding="utf-8")

    def test_only_one_piecewise_parent_cell(self) -> None:
        run = self.manifest["run_identity"]
        self.assertEqual(run["tensor_parallel"], 1)
        self.assertEqual(run["mtp_depth"], 0)
        self.assertEqual(run["kv_cache_dtype"], "fp8_e4m3")
        self.assertEqual(run["graph_mode"], "PIECEWISE")
        self.assertEqual(self.manifest["exact_depth_contract"]["depths"], [8192])
        self.assertTrue(self.manifest["execution"]["one_gpu_server_lifetime"])

    def test_eager_curve_authorization_is_pinned(self) -> None:
        evidence = self.manifest["authorization_evidence"]
        self.assertEqual(evidence["terminal_state"], "passed-quality-clean-expansion")
        self.assertEqual(evidence["passed_depth_count"], 6)
        self.assertTrue(evidence["full_quality_passed"])
        self.assertTrue(evidence["cleanup_passed"])
        self.assertEqual(
            evidence["terminal_receipt_sha256"],
            "ddf2d160dac21c5e110417410c84a113c0c89c2db2c0fa41a53943efad3d9eef",
        )
        self.assertIn("eager E4M3 curve authorization receipt failed", self.runner)

    def test_exact_piecewise_identity_markers(self) -> None:
        for token in (
            "--kv-cache-dtype fp8_e4m3",
            "VLLM_XPU_ENABLE_XPU_GRAPH=1",
            'cudagraph_mode":"PIECEWISE',
            "kv_cache_dtype=fp8_e4m3",
            "enforce_eager=False",
            "quantization=inc",
            "Capturing CUDA graphs (mixed prefill-decode, PIECEWISE)",
            "Graph capturing finished",
            "Capturing CUDA graphs (decode, FULL)",
        ):
            self.assertIn(token, self.runner)
        self.assertNotIn("--enforce-eager", self.runner)

    def test_exact_depth_and_full_quality(self) -> None:
        self.assertIn("--depth 8192", self.runner)
        self.assertIn("--context-capacity 32896", self.runner)
        self.assertIn("--require-baseline", self.runner)
        self.assertEqual(self.runner.count("dockerc run -d"), 1)

    def test_nonreplacement_and_no_automatic_expansion(self) -> None:
        interpretation = self.manifest["interpretation"]
        self.assertIsNone(interpretation["speed_floor"])
        self.assertFalse(interpretation["historical_replacement_allowed"])
        self.assertFalse(interpretation["graph_depth_expansion_is_automatic"])

    def test_runner_is_inert_and_cleanup_is_global(self) -> None:
        for token in (
            "--check",
            "--plan",
            "--execute",
            "exact acknowledgement required",
            "repository must be clean",
            "fresh campaign roots",
            "trap cleanup_on_exit EXIT",
            "trap 'exit 130' INT",
            "trap 'exit 143' TERM",
            "strict_postcleanup",
            "canonical GPU campaign lock",
        ):
            self.assertIn(token, self.runner)

    def test_clean_main_failure_is_propagated(self) -> None:
        self.assertIn(
            'launch_head=$(require_clean_pushed_main) || die "clean pushed main check failed"',
            self.runner,
        )


if __name__ == "__main__":
    unittest.main()
