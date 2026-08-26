#!/usr/bin/env python3
"""Inert contract tests for the official-f01e AutoRound E5M2-KV sentinel."""

from __future__ import annotations

import json
import pathlib
import unittest


REPO = pathlib.Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-26-qwen38-official-f01e-autoround-tp1-e5m2kv-init-canary-r1-prereg.json"
RUNNER = LANE / "scripts/run-20260826-qwen38-official-f01e-autoround-tp1-e5m2kv-init-canary-r1.sh"


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.runner = RUNNER.read_text(encoding="utf-8")

    def test_one_init_canary_cell_only(self) -> None:
        run = self.manifest["run_identity"]
        self.assertEqual(run["tensor_parallel"], 1)
        self.assertEqual(run["mtp_depth"], 0)
        self.assertEqual(run["kv_cache_dtype"], "fp8_e5m2")
        self.assertEqual(run["graph_mode"], "off")
        self.assertEqual(self.manifest["exact_depth_contract"]["depths"], [128])
        self.assertTrue(self.manifest["execution"]["one_gpu_server_lifetime"])

    def test_old_hard_refusal_is_disclosed(self) -> None:
        prior = self.manifest["prior_evidence"]
        self.assertEqual(prior["classification"], "hard-refused at engine initialization")
        self.assertIn("does not support fp8_e5m2", prior["exact_error"])

    def test_exact_identity_and_one_lifetime(self) -> None:
        run = self.manifest["run_identity"]
        self.assertEqual(
            run["image_id"],
            "sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f",
        )
        self.assertEqual(run["vllm_commit"], "ac7509e2b1db40fec2f03dde1ed4e9dfdc2338c9")
        self.assertEqual(self.runner.count("dockerc run -d"), 1)

    def test_quality_runs_only_after_canary(self) -> None:
        self.assertIn("if (( depth_rc == 0 )); then", self.runner)
        self.assertIn("skipped: exact canary failed", self.runner)
        self.assertIn("--depth 128", self.runner)
        self.assertIn("--case-id canary-128", self.runner)
        self.assertIn("--require-baseline", self.runner)

    def test_unsupported_requires_exact_image_and_specific_line(self) -> None:
        body = self.runner.split("explicit_e5m2_unsupported()", 1)[1].split(
            "write_arm_result()", 1
        )[0]
        for token in (
            '"$(<"$root/image-id.txt")" == "$image_id"',
            "fp8[_ -]?e5m2",
            "kv[_ -]?cache|kv_cache_dtype",
            "not supported|unsupported|invalid (value|dtype)|does not support",
        ):
            self.assertIn(token, body)

    def test_historical_results_are_immutable(self) -> None:
        interpretation = self.manifest["interpretation"]
        self.assertIsNone(interpretation["speed_floor"])
        self.assertFalse(interpretation["historical_replacement_allowed"])
        self.assertFalse(interpretation["prior_e5m2_closure_replacement_allowed"])
        self.assertFalse(interpretation["descendant_expansion_is_automatic"])

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
