#!/usr/bin/env python3
"""Inert tests for the f01e AutoRound PIECEWISE E4M3 depth expansion."""

from __future__ import annotations

import json
import pathlib
import unittest


REPO = pathlib.Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-26-qwen38-official-f01e-autoround-tp1-e4m3kv-piecewise-depth-expansion-r1-prereg.json"
RUNNER = LANE / "scripts/run-20260826-qwen38-official-f01e-autoround-tp1-e4m3kv-piecewise-depth-expansion-r1.sh"


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.runner = RUNNER.read_text(encoding="utf-8")

    def test_identical_piecewise_e4m3_identity(self) -> None:
        run = self.manifest["run_identity"]
        self.assertEqual(run["tensor_parallel"], 1)
        self.assertEqual(run["mtp_depth"], 0)
        self.assertEqual(run["kv_cache_dtype"], "fp8_e4m3")
        self.assertEqual(run["graph_mode"], "PIECEWISE")
        self.assertEqual(
            self.manifest["exact_depth_contract"]["depths"],
            [2048, 4096, 8192, 16384, 24576, 32768],
        )

    def test_piecewise_sentinel_authorization_is_pinned(self) -> None:
        evidence = self.manifest["authorization_evidence"]
        self.assertEqual(evidence["terminal_state"], "passed-quality-clean-sentinel")
        self.assertTrue(evidence["exact_8k_gate_passed"])
        self.assertTrue(evidence["full_quality_passed"])
        self.assertTrue(evidence["cleanup_passed"])
        self.assertEqual(
            evidence["terminal_receipt_sha256"],
            "7f271faf8492e9c2634e494df653dee7f48f5aa3a7b37d180bf3bb34016adcb6",
        )
        self.assertIn("PIECEWISE E4M3 sentinel authorization receipt failed", self.runner)

    def test_one_lifetime_six_receipts_and_full_quality(self) -> None:
        self.assertTrue(self.manifest["execution"]["one_gpu_server_lifetime"])
        self.assertEqual(self.runner.count("dockerc run -d"), 1)
        self.assertIn('depths=(2048 4096 8192 16384 24576 32768)', self.runner)
        self.assertIn('for depth in "${depths[@]}"', self.runner)
        self.assertIn("--context-capacity 32896", self.runner)
        self.assertIn("--require-baseline", self.runner)

    def test_piecewise_markers_are_fail_closed(self) -> None:
        for token in (
            "--kv-cache-dtype fp8_e4m3",
            "VLLM_XPU_ENABLE_XPU_GRAPH=1",
            'cudagraph_mode":"PIECEWISE',
            "kv_cache_dtype=fp8_e4m3",
            "enforce_eager=False",
            "Capturing CUDA graphs (mixed prefill-decode, PIECEWISE)",
            "Graph capturing finished",
            "Capturing CUDA graphs (decode, FULL)",
            "depth_passed == 6 && quality_rc == 0",
        ):
            self.assertIn(token, self.runner)
        self.assertNotIn("--enforce-eager", self.runner)

    def test_nonreplacement_and_publication_are_explicit(self) -> None:
        interpretation = self.manifest["interpretation"]
        self.assertIsNone(interpretation["speed_floor"])
        self.assertFalse(interpretation["historical_replacement_allowed"])
        self.assertFalse(interpretation["site_publication_is_automatic"])

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
