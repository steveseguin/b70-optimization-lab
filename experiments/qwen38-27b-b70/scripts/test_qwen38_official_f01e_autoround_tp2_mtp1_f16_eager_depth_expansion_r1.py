#!/usr/bin/env python3
"""Inert contract tests for the current-f01e TP2/MTP1 depth expansion."""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import unittest


REPO = pathlib.Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp1-f16-eager-depth-expansion-r1-prereg.json"
RUNNER = LANE / "scripts/run-20260826-qwen38-official-f01e-autoround-tp2-mtp1-f16-eager-depth-expansion-r1.sh"
DEPTHS = [2048, 4096, 8192, 16384, 24576, 32768]


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.runner = RUNNER.read_text(encoding="utf-8")

    def test_exact_tp2_mtp1_identity(self) -> None:
        run = self.manifest["run_identity"]
        self.assertEqual((run["tensor_parallel"], run["mtp_depth"]), (2, 1))
        self.assertEqual(run["speculative_config"], {"method": "qwen3_next_mtp", "num_speculative_tokens": 1})
        self.assertEqual(run["startup_speculator_identity"], {"method": "mtp", "num_spec_tokens": 1})
        self.assertEqual(run["gpu_affinity"], "0,1")
        self.assertEqual(run["gpu_memory_utilization"], 0.6)
        self.assertEqual(run["graph_mode"], "off")
        self.assertEqual(run["kv_cache_dtype"], "float16")

    def test_native_speculator_argument_and_startup_gate(self) -> None:
        for token in (
            '--speculative-config \'{"method":"qwen3_next_mtp","num_speculative_tokens":1}\'',
            "speculative_config=SpeculativeConfig(method='mtp'",
            "num_spec_tokens=1",
            "embedded MTP tensor binding contract failed",
            "94102b67c6b84e65dbb9bae37c00bd88ac1a43ff577ce65fd8842d231c7e89de",
        ):
            self.assertIn(token, self.runner)
        self.assertNotIn("ONEAPI_DEVICE_SELECTOR", self.runner)
        self.assertNotIn("--kv-cache-dtype", self.runner)

    def test_six_same_topology_mtp0_targets_are_frozen_and_never_tp1(self) -> None:
        targets = self.manifest["target_oracles"]
        expected = {
            "2048": "57b1ad5760ab790c3b839a897bc6b1807a2d1037710b0e949e2977973cc5864e",
            "4096": "6e32b0a05f7e355bf21c5e3ebd0e04a16fbf3d54bc39890aa8740b3a5430f187",
            "8192": "55bc2ad94cb920dda1233f3d26209d009a80549469974182c0455d2826f11266",
            "16384": "c93e67650b0bf61941f33280dd66a2de82b555c4d65b0a0ddc1093defb03d569",
            "24576": "eaef51ab0c3ad12501d1f9b087233359b3a6455cce25bb68161828cd61600fa0",
            "32768": "cf37631f2d2d32fb0dfbc7ab1674b9cccdf67270791fc728112dbd2a458edc9b",
        }
        self.assertEqual({k: v["sha256"] for k, v in targets["depth_receipts"].items()}, expected)
        self.assertEqual(targets["terminal_sha256"], "63fe2e8a85db47af331743b93b1c6e181f930775104f19483eb7b9e1da0f2c60")
        self.assertEqual(targets["quality_sha256"], "ef15f39a848d262a4582b1ab6c9a2f10713ecfbcae02497bc4462c8ae5a3af96")
        self.assertNotIn("autoround-tp1-", self.runner.lower())
        self.assertNotIn("tp1_target", self.runner.lower())

    def test_no_mtp1_parent_is_fabricated(self) -> None:
        policy = self.manifest["parent_policy"]
        self.assertFalse(policy["mtp1_sentinel_available"])
        self.assertNotIn("parent_sentinel", self.manifest)
        for token in ("parent_root=", "parent_8k=", "parent_terminal=", "parent_ok", "parent_8k_match"):
            self.assertNotIn(token, self.runner)

    def test_six_depths_one_lifetime_and_isolated_counter_snapshots(self) -> None:
        self.assertEqual(self.manifest["exact_depth_contract"]["depths"], DEPTHS)
        self.assertIn("depths=(2048 4096 8192 16384 24576 32768)", self.runner)
        self.assertIn('for depth in "${depths[@]}"', self.runner)
        body = self.runner.split('for depth in "${depths[@]}"', 1)[1]
        self.assertLess(body.index("depth-$depth.before.prom"), body.index('"$depth_helper" --execute'))
        self.assertLess(body.index('"$depth_helper" --execute'), body.index("depth-$depth.after.prom"))
        self.assertEqual(self.runner.count("dockerc run -d"), 1)

    def test_acceptance_is_finite_positive_conserved_and_nondecreasing(self) -> None:
        for token in (
            "math.isfinite(value)", "a_draft >= b_draft", "a_accept >= b_accept",
            "drafted > 0", "0 < accepted <= drafted", "acceptance_passes",
        ):
            self.assertIn(token, self.runner)
        self.assertIn("same_topology_target_verification", self.runner)
        self.assertIn("candidate_ids == target_ids", self.runner)

    def test_per_depth_validity_and_partial_freeze_are_exact(self) -> None:
        for token in (
            '"per_depth_valid": rc == 0 and acceptance_ok and target_ok',
            'if item["per_depth_valid"]',
            'native_oracle_states = oracle_states | {"partial-depth-expansion"}',
            "state=partial-depth-expansion",
            '"failed_or_quarantined_depths"',
        ):
            self.assertIn(token, self.runner)

    def test_quality_all16_and_same_topology_baseline_are_required(self) -> None:
        quality = self.manifest["quality_contract"]
        self.assertIn("tp2-mtp0", quality["baseline"])
        self.assertEqual(quality["baseline_sha256"], "ef15f39a848d262a4582b1ab6c9a2f10713ecfbcae02497bc4462c8ae5a3af96")
        match = re.search(r"quality_objective_gate\(\) \{\n  jq -e '(.*?)' \"\$1\"\n\}", self.runner, re.DOTALL)
        self.assertIsNotNone(match)
        jq_filter = match.group(1)
        usage = lambda value=0: {"prompt_tokens_details": {"cached_tokens": value}}
        payload = {"pass_all": True, "exact_cases": [{"usage": usage()} for _ in range(7)],
                   "repeat_case": {"runs": [{"usage": usage()} for _ in range(8)]},
                   "long_context_case": {"usage": usage()}}
        self.assertEqual(subprocess.run(["jq", "-e", jq_filter], input=json.dumps(payload), text=True,
                                       capture_output=True).returncode, 0)
        payload["repeat_case"]["runs"][2]["usage"] = {"prompt_tokens_details": {}}
        self.assertNotEqual(subprocess.run(["jq", "-e", jq_filter], input=json.dumps(payload), text=True,
                                          capture_output=True).returncode, 0)
        self.assertIn("quality_rc != 0 || objective_quality_ok == 0 || baseline_ok == 0", self.runner)

    def test_topology_cache_cleanup_and_fresh_identity_are_preserved(self) -> None:
        for token in (
            "port=19493", "--tensor-parallel-size 2", "--gpu-memory-utilization 0.60",
            "ZE_AFFINITY_MASK=0,1", "VLLM_XPU_ENABLE_XPU_GRAPH=0",
            "world_size=2, local_world_size=2", "rank_${rank}_0",
            "rank-cache-isolation-gate-failed", "strict_postcleanup", "trap cleanup_on_exit EXIT",
        ):
            self.assertIn(token, self.runner)

    def test_input_provenance_has_explicit_files_not_directories(self) -> None:
        self.assertIn('"$target_depth_root/depth-2048.json"', self.runner)
        self.assertIn('"$target_depth_root/depth-32768.json"', self.runner)
        self.assertIn('"$target_result"', self.runner)
        self.assertNotIn('"$target_root" > "$root/input-sha256sums.txt"', self.runner)

    def test_protected_values_and_default_inertness(self) -> None:
        interpretation = self.manifest["interpretation"]
        self.assertIsNone(interpretation["speed_floor"])
        self.assertEqual(interpretation["protected_decode_values_unchanged"], [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144])
        self.assertFalse(interpretation["historical_replacement_allowed"])
        self.assertFalse(interpretation["site_publication_automatic"])
        self.assertFalse(interpretation["descendant_execution_authorized"])
        self.assertTrue(self.manifest["execution"]["default_is_inert"])
        self.assertIn("exact acknowledgement required", self.runner)


if __name__ == "__main__":
    unittest.main()
