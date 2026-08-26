#!/usr/bin/env python3
"""Inert tests for the f01e AutoRound TP1 MTP3/F16 parent sentinel."""

from __future__ import annotations

import json
import pathlib
import unittest


REPO = pathlib.Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-26-qwen38-official-f01e-autoround-tp1-mtp3-f16-eager-8k-sentinel-r1-prereg.json"
RUNNER = LANE / "scripts/run-20260826-qwen38-official-f01e-autoround-tp1-mtp3-f16-eager-8k-sentinel-r1.sh"


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.runner = RUNNER.read_text(encoding="utf-8")

    def test_exact_mtp3_f16_eager_parent(self) -> None:
        run = self.manifest["run_identity"]
        self.assertEqual(run["tensor_parallel"], 1)
        self.assertEqual(run["mtp_depth"], 3)
        self.assertEqual(run["kv_cache_dtype"], "float16")
        self.assertEqual(run["graph_mode"], "off")
        self.assertEqual(self.manifest["exact_depth_contract"]["depths"], [8192])
        self.assertTrue(self.manifest["execution"]["one_gpu_server_lifetime"])

    def test_no_external_draft_and_embedded_binding_is_pinned(self) -> None:
        binding = self.manifest["speculator_binding"]
        self.assertIn("no external draft model", binding["type"])
        self.assertEqual(binding["method_requested"], "qwen3_next_mtp")
        self.assertEqual(binding["method_resolved_expected"], "mtp")
        self.assertEqual(binding["num_speculative_tokens"], 3)
        self.assertEqual(binding["mtp_num_hidden_layers"], 1)
        self.assertEqual(binding["mtp_tensor_count"], 29)
        self.assertEqual(
            binding["mtp_tensor_sha256"],
            "94102b67c6b84e65dbb9bae37c00bd88ac1a43ff577ce65fd8842d231c7e89de",
        )
        self.assertIn("embedded MTP tensor binding contract failed", self.runner)

    def test_exact_speculative_args_and_startup_markers(self) -> None:
        for token in (
            "--enforce-eager",
            '--speculative-config \'{\"method\":\"qwen3_next_mtp\",\"num_speculative_tokens\":3}\'',
            "SpeculativeConfig(method='mtp'",
            "num_spec_tokens=3",
            "quantization=inc",
            "enforce_eager=True",
            "kv_cache_dtype=auto",
        ):
            self.assertIn(token, self.runner)
        self.assertNotIn("--kv-cache-dtype", self.runner)
        self.assertNotIn("VLLM_XPU_ENABLE_XPU_GRAPH", self.runner)

    def test_acceptance_is_isolated_to_exact_request(self) -> None:
        body = self.runner.split("run_sentinel()", 1)[1].split("action=help", 1)[0]
        before = body.index('metrics.before.prom')
        depth = body.index('"$depth_helper" --execute')
        after = body.index('metrics.after-depth.prom')
        quality = body.index('"$quality_helper" --base-url')
        self.assertLess(before, depth)
        self.assertLess(depth, after)
        self.assertLess(after, quality)
        self.assertIn("drafted > 0", self.runner)
        self.assertIn("0 < accepted <= drafted", self.runner)

    def test_target_oracle_is_pinned_and_exact(self) -> None:
        oracle = self.manifest["exact_depth_contract"]["target_oracle"]
        self.assertEqual(
            oracle["sha256"],
            "94f7d11862b2e35b057e7a95b3d529b89a4c2857d8886ce93e4b4d85b7385c34",
        )
        self.assertEqual(
            oracle["output_token_ids_sha256"],
            "34e792ccf3c1d795b686750f27990de2ca605c22046c97b3fff8ad0a7fc82e53",
        )
        self.assertIn("candidate_ids == target_ids", self.runner)
        self.assertIn("conservative cross-boot gate", self.runner)

    def test_pass_requires_every_mechanism_and_quality_gate(self) -> None:
        self.assertIn(
            "depth_rc == 0 && quality_rc == 0 && acceptance_ok == 1 && target_ok == 1",
            self.runner,
        )
        self.assertIn("--require-baseline", self.runner)
        self.assertEqual(self.runner.count("dockerc run -d"), 1)

    def test_unsupported_and_binding_failure_are_distinct(self) -> None:
        self.assertIn("explicit_speculator_unsupported", self.runner)
        self.assertIn("explicit_speculator_binding_failed", self.runner)
        self.assertIn("startup-failed-without-explicit-speculator-classification", self.runner)

    def test_nonreplacement_and_cleanup(self) -> None:
        interpretation = self.manifest["interpretation"]
        self.assertIsNone(interpretation["speed_floor"])
        self.assertFalse(interpretation["historical_replacement_allowed"])
        self.assertFalse(interpretation["descendant_expansion_is_automatic"])
        for token in (
            "--check",
            "--plan",
            "--execute",
            "repository must be clean",
            "trap cleanup_on_exit EXIT",
            "trap 'exit 130' INT",
            "trap 'exit 143' TERM",
            "strict_postcleanup",
            "canonical GPU campaign lock",
        ):
            self.assertIn(token, self.runner)

    def test_mtp4_failure_limits_are_explicit(self) -> None:
        evidence = self.manifest["prior_evidence"]["current_f01e_mtp4_limit"]
        self.assertIn("token 99", evidence["cross_boot_8k"])
        self.assertIn("Expected spec_token", evidence["fatal_32k"])
        self.assertIn("separately preregistered", evidence["consequence"])

    def test_clean_main_failure_is_propagated(self) -> None:
        self.assertIn(
            'launch_head=$(require_clean_pushed_main) || die "clean pushed main check failed"',
            self.runner,
        )


if __name__ == "__main__":
    unittest.main()
