#!/usr/bin/env python3
"""Inert tests for the f01e AutoRound TP1 MTP2/F16 depth expansion."""

from __future__ import annotations

import json
import pathlib
import unittest


REPO = pathlib.Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-26-qwen38-official-f01e-autoround-tp1-mtp2-f16-eager-depth-expansion-r1-prereg.json"
RUNNER = LANE / "scripts/run-20260826-qwen38-official-f01e-autoround-tp1-mtp2-f16-eager-depth-expansion-r1.sh"


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.runner = RUNNER.read_text(encoding="utf-8")

    def test_exact_identity_and_six_depths(self) -> None:
        run = self.manifest["run_identity"]
        self.assertEqual(run["tensor_parallel"], 1)
        self.assertEqual(run["mtp_depth"], 2)
        self.assertEqual(run["kv_cache_dtype"], "float16")
        self.assertEqual(run["graph_mode"], "off")
        self.assertEqual(
            self.manifest["exact_depth_contract"]["depths"],
            [2048, 4096, 8192, 16384, 24576, 32768],
        )

    def test_parent_authorization_is_pinned(self) -> None:
        auth = self.manifest["authorization_evidence"]
        self.assertEqual(auth["terminal_state"], "quarantined-target-verification-failed")
        self.assertEqual(auth["drafted_tokens"], 94)
        self.assertEqual(auth["accepted_tokens"], 82)
        self.assertFalse(auth["exact_target_token_parity"])
        self.assertEqual(auth["first_target_divergence_one_based"], 99)
        self.assertTrue(auth["full_quality_passed"])
        self.assertTrue(auth["diagnostic_expansion_authorized_by_user"])
        self.assertEqual(
            auth["terminal_receipt_sha256"],
            "cfd79841d1a82e7cf4fd5bc5670626369fa0e7c373c5f80c9d2a3f9f4f6aa012",
        )
        self.assertIn("MTP2 diagnostic parent evidence receipt failed", self.runner)

    def test_six_target_oracles_are_pinned(self) -> None:
        oracles = self.manifest["exact_depth_contract"]["target_oracles"]
        self.assertEqual([o["depth"] for o in oracles], [2048, 4096, 8192, 16384, 24576, 32768])
        self.assertEqual(len({o["sha256"] for o in oracles}), 6)
        self.assertEqual(len({o["output_token_ids_sha256"] for o in oracles}), 6)
        for depth in (2048, 4096, 8192, 16384, 24576, 32768):
            self.assertIn(f'"$target_root/depth-{depth}.json"', self.runner)

    def test_per_depth_counter_bracketing(self) -> None:
        body = self.runner.split("run_expansion()", 1)[1].split("action=help", 1)[0]
        self.assertIn('for depth in "${depths[@]}"', body)
        before = body.index('depth-$depth.before.prom')
        request = body.index('"$depth_helper" --execute')
        after = body.index('depth-$depth.after.prom')
        verify = body.index('write_acceptance_and_target')
        quality = body.index('"$quality_helper" --base-url')
        self.assertLess(before, request)
        self.assertLess(request, after)
        self.assertLess(after, verify)
        self.assertLess(verify, quality)
        self.assertIn("drafted > 0", self.runner)
        self.assertIn("0 < accepted <= drafted", self.runner)

    def test_pass_requires_all_six_mechanism_gates(self) -> None:
        self.assertIn(
            "depth_passed == 6 && acceptance_passed == 6 && target_passed == 6 && quality_rc == 0",
            self.runner,
        )
        self.assertIn("--require-baseline", self.runner)
        self.assertEqual(self.runner.count("dockerc run -d"), 1)
        self.assertIn("passed-diagnostic-quality-clean-expansion", self.runner)
        self.assertIn('"publication_authorized": False', self.runner)

    def test_32k_engine_fatal_is_explicit_and_precedes_generic_failure(self) -> None:
        self.assertIn("explicit_32k_engine_fatal", self.runner)
        self.assertIn("failed-32k-engine-fatal", self.runner)
        classification = self.runner.split("if (( cleanup_ok == 0 ))", 1)[1]
        self.assertLess(classification.index("fatal_32k == 1"), classification.index("runner_rc != 0"))
        self.assertIn("known_32k_risk", self.manifest["prior_evidence"])

    def test_embedded_native_binding_remains_exact(self) -> None:
        binding = self.manifest["speculator_binding"]
        self.assertIn("no external draft model", binding["type"])
        self.assertEqual(binding["num_speculative_tokens"], 2)
        self.assertEqual(binding["mtp_tensor_count"], 29)
        self.assertIn('--speculative-config \'{\"method\":\"qwen3_next_mtp\",\"num_speculative_tokens\":2}\'', self.runner)
        self.assertNotIn("--kv-cache-dtype", self.runner)
        self.assertNotIn("VLLM_XPU_ENABLE_XPU_GRAPH", self.runner)

    def test_nonreplacement_and_cleanup(self) -> None:
        interpretation = self.manifest["interpretation"]
        self.assertIsNone(interpretation["speed_floor"])
        self.assertFalse(interpretation["historical_replacement_allowed"])
        self.assertFalse(interpretation["site_publication_is_automatic"])
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

    def test_clean_main_failure_is_propagated(self) -> None:
        self.assertIn(
            'launch_head=$(require_clean_pushed_main) || die "clean pushed main check failed"',
            self.runner,
        )


if __name__ == "__main__":
    unittest.main()
