#!/usr/bin/env python3
"""Inert tests for the current-f01e TP1/MTP1 eager E4M3 exact-4K sentinel."""

import json
import importlib.util
import pathlib
import unittest

REPO = pathlib.Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-26-qwen38-official-f01e-autoround-tp1-mtp1-e4m3kv-eager-4k-sentinel-r1-prereg.json"
RUNNER = LANE / "scripts/run-20260826-qwen38-official-f01e-autoround-tp1-mtp1-e4m3kv-eager-4k-sentinel-r1.sh"


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST.read_text())
        cls.runner = RUNNER.read_text()

    def test_exact_identity(self):
        run = self.manifest["run_identity"]
        self.assertEqual((run["tensor_parallel"], run["mtp_depth"], run["kv_cache_dtype"]), (1, 1, "fp8_e4m3"))
        self.assertTrue(run["enforce_eager"])
        self.assertEqual(self.manifest["exact_depth_contract"]["depths"], [4096])
        self.assertIn("--kv-cache-dtype fp8_e4m3", self.runner)
        self.assertIn("kv_cache_dtype=fp8_e4m3", self.runner)
        self.assertNotIn("VLLM_XPU_ENABLE_XPU_GRAPH", self.runner)

    def test_dual_parent_roles_are_not_confused(self):
        parents = self.manifest["parent_evidence"]
        self.assertEqual(parents["e4m3_mtp0_target"]["output_token_ids_sha256"], "a3d7ad63a22cfb897d9d7f69952e30e2036617776d18fb4c8a9be1513da522cd")
        self.assertIn("not a token oracle", parents["f16_mtp1_mechanism_parent"]["role"])
        self.assertEqual((parents["f16_mtp1_mechanism_parent"]["accepted_tokens"], parents["f16_mtp1_mechanism_parent"]["drafted_tokens"]), (56, 71))
        self.assertIn("candidate_ids == target_ids", self.runner)

    def test_exact_coverage_cell_is_missing_and_only_one_is_authorized(self):
        coverage = self.manifest["coverage_contract"]
        self.assertEqual(coverage["id"], "qwen38-tp1-vllm-xpu-autoround-mtp-matrix")
        self.assertEqual(coverage["preregistration_state"], "missing")
        self.assertEqual(coverage["other_cells_authorized"], 0)
        family = json.loads((REPO / coverage["path"]).read_text())
        contract = next(item for item in family["coverage_contracts"] if item["id"] == coverage["id"])
        module_path = REPO / "tools/build-family-pages.py"
        spec = importlib.util.spec_from_file_location("build_family_pages_for_mtp1_e4m3", module_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cells, errors = module.expand_coverage_contract(contract)
        self.assertEqual(errors, [])
        target = next(cell for cell in cells if cell["selectors"] == coverage["selectors"])
        self.assertEqual(target["state"], "missing")
        self.assertEqual(target["rule_ids"], ["default-exact-gap"])

    def test_acceptance_is_isolated(self):
        body = self.runner.split("run_sentinel()", 1)[1].split("action=help", 1)[0]
        before = body.index("metrics.before.prom")
        depth = body.index('"$depth_helper" --execute')
        after = body.index("metrics.after-depth.prom")
        quality = body.index('"$quality_helper" --base-url')
        self.assertLess(before, depth)
        self.assertLess(depth, after)
        self.assertLess(after, quality)
        self.assertIn("drafted > 0", self.runner)
        self.assertIn("0 < accepted <= drafted", self.runner)

    def test_pass_is_fail_closed(self):
        self.assertIn("depth_rc == 0 && quality_rc == 0 && acceptance_ok == 1 && target_ok == 1", self.runner)
        self.assertIn("--require-baseline", self.runner)
        self.assertIn("--long-context-tokens 8192", self.runner)
        self.assertEqual(self.runner.count("dockerc run -d"), 1)

    def test_zero_automatic_authority(self):
        policy = self.manifest["interpretation"]
        self.assertFalse(policy["automatic_publication"])
        self.assertEqual(policy["site_cells_filled_automatically"], 0)
        self.assertFalse(policy["descendant_expansion_is_automatic"])
        self.assertFalse(policy["historical_replacement_allowed"])
        self.assertIn('"publication_authorized": False', self.runner)
        self.assertIn('"descendant_expansion_authorized": False', self.runner)

    def test_terminal_states_are_frozen_without_speed_authority(self):
        states = self.manifest["terminal_classification"]
        self.assertEqual(
            set(states),
            {
                "passed-quality-clean-sentinel",
                "quarantined-acceptance-failed",
                "quarantined-target-verification-failed",
                "quarantined-quality-failed",
                "quarantined-exact-depth-failed",
                "unsupported",
                "failed",
            },
        )
        self.assertTrue(all("publication" not in text or "without speed publication" in text for text in states.values()))

    def test_inert_clean_and_cleanup_gates(self):
        for token in ("--check", "--plan", "--execute", "repository must be clean", "trap cleanup_on_exit EXIT", "strict_postcleanup", "canonical GPU campaign lock"):
            self.assertIn(token, self.runner)
        self.assertIn('launch_head=$(require_clean_pushed_main) || die "clean pushed main check failed"', self.runner)

    def test_embedded_speculator_is_pinned(self):
        binding = self.manifest["speculator_binding"]
        self.assertIn("no external draft model", binding["type"])
        self.assertEqual(binding["mtp_tensor_count"], 29)
        self.assertEqual(binding["mtp_tensor_sha256"], "94102b67c6b84e65dbb9bae37c00bd88ac1a43ff577ce65fd8842d231c7e89de")


if __name__ == "__main__":
    unittest.main()
