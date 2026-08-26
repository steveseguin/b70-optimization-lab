#!/usr/bin/env python3
"""Inert contract tests for the official-f01e E4M3-KV depth expansion."""

from __future__ import annotations

import json
import pathlib
import unittest


REPO = pathlib.Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-26-qwen38-official-f01e-autoround-tp1-e4m3kv-depth-expansion-r1-prereg.json"
RUNNER = LANE / "scripts/run-20260826-qwen38-official-f01e-autoround-tp1-e4m3kv-depth-expansion-r1.sh"


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.runner = RUNNER.read_text(encoding="utf-8")

    def test_only_identical_eager_e4m3_identity_expands(self) -> None:
        run = self.manifest["run_identity"]
        self.assertEqual(run["tensor_parallel"], 1)
        self.assertEqual(run["mtp_depth"], 0)
        self.assertEqual(run["kv_cache_dtype"], "fp8_e4m3")
        self.assertEqual(run["graph_mode"], "off")
        self.assertEqual(
            self.manifest["exact_depth_contract"]["depths"],
            [2048, 4096, 8192, 16384, 24576, 32768],
        )

    def test_sentinel_authorization_is_pinned(self) -> None:
        evidence = self.manifest["authorization_evidence"]
        self.assertEqual(evidence["terminal_state"], "passed-quality-clean-sentinel")
        self.assertTrue(evidence["exact_8k_gate_passed"])
        self.assertTrue(evidence["full_quality_passed"])
        self.assertTrue(evidence["cleanup_passed"])
        self.assertEqual(
            evidence["terminal_receipt_sha256"],
            "1fabe9e75cbf3edb13baa3775e33dced1ad16034267f786a2b84bc17493b12ba",
        )
        self.assertIn("sentinel authorization receipt failed", self.runner)

    def test_one_server_lifetime_and_six_receipts(self) -> None:
        self.assertTrue(self.manifest["execution"]["one_gpu_server_lifetime"])
        self.assertEqual(self.runner.count("dockerc run -d"), 1)
        self.assertIn('depths=(2048 4096 8192 16384 24576 32768)', self.runner)
        self.assertIn('for depth in "${depths[@]}"', self.runner)
        self.assertIn('--context-capacity 32896', self.runner)

    def test_full_quality_and_eager_identity_are_gated(self) -> None:
        for token in (
            "--kv-cache-dtype fp8_e4m3",
            "--enforce-eager",
            "kv_cache_dtype=fp8_e4m3",
            "enforce_eager=True",
            "quantization=inc",
            "Graph capturing finished",
            "--require-baseline",
            "depth_passed == 6 && quality_rc == 0",
        ):
            self.assertIn(token, self.runner)
        self.assertNotIn("VLLM_XPU_ENABLE_XPU_GRAPH", self.runner)

    def test_nonreplacement_and_publication_are_explicit(self) -> None:
        interpretation = self.manifest["interpretation"]
        self.assertIsNone(interpretation["speed_floor"])
        self.assertFalse(interpretation["historical_replacement_allowed"])
        self.assertFalse(interpretation["prior_e4m3_value_replacement_allowed"])
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
