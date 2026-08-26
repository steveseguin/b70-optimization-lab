#!/usr/bin/env python3
"""Inert contract tests for the current-f01e TP4/MTP1 depth expansion."""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import unittest


REPO = pathlib.Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-26-qwen38-official-f01e-autoround-tp4-mtp1-f16-eager-depth-expansion-r1-prereg.json"
RUNNER = LANE / "scripts/run-20260826-qwen38-official-f01e-autoround-tp4-mtp1-f16-eager-depth-expansion-r1.sh"
DEPTHS = [2048, 4096, 8192, 16384, 24576, 32768]


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.runner = RUNNER.read_text(encoding="utf-8")

    def test_exact_tp4_mtp1_identity(self) -> None:
        run = self.manifest["run_identity"]
        self.assertEqual((run["tensor_parallel"], run["mtp_depth"]), (4, 1))
        self.assertEqual(run["speculative_config"], {"method": "qwen3_next_mtp", "num_speculative_tokens": 1})
        self.assertEqual(run["startup_speculator_identity"], {"method": "mtp", "num_spec_tokens": 1})
        self.assertEqual(run["gpu_affinity"], "0,1,2,3")
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
            "2048": "614eba447a944a87114f0b117b7148d4cf009deb356d5c2f5ed5cf3b9b68ea1e",
            "4096": "1dbba43c7ed816156f53b489e2287247e8a96f26a7d5f15a1a381d28f7e89e02",
            "8192": "a4a898748454b9d2588fd911c9e38ddfff58a129736db3a97ce1b871c5f472dc",
            "16384": "d0a621857ecd56e7b2cb44ec07381b5e4ebfbd3e0df322fdc741f92f0715481a",
            "24576": "13122dd794bd0e9106450224b5a19261585a2740a9b293e787e8e6a74e4fd4b6",
            "32768": "1ebe52108c16706a2995ee9981509dcada252e1961c9eaeb3b321a3e460545e4",
        }
        self.assertEqual({k: v["sha256"] for k, v in targets["depth_receipts"].items()}, expected)
        self.assertEqual(targets["terminal_sha256"], "f6ed578228a9e6c21c68653b828a0ecc4ee776107337446e6ecc2f595d47297e")
        self.assertEqual(targets["quality_sha256"], "2172c3bdba148062487ba73980fee46a5f1f2501baa37ceb83ca0e058bcaa83f")
        self.assertNotIn("autoround-tp1-", self.runner.lower())
        self.assertNotIn("tp1_target", self.runner.lower())

    def test_mtp1_8k_parent_is_hard_and_pinned(self) -> None:
        parent = self.manifest["parent_sentinel"]
        self.assertEqual(parent["terminal_sha256"], "2ee36705a315f86c8ead14cfbee086f3b4d54a185cb7ff13d8a92f17d8bc8218")
        self.assertEqual(parent["exact_8k_sha256"], "e8dddbc89c5144b40a55d354b6ba42ecfecb77a0d9734825e9fc169ed9bbcdbc")
        self.assertEqual(parent["verification_sha256"], "786d8bd9a41458e896f76847c9b135a6a282aaa27b83b8cf10ea1a8b2a61fa9c")
        self.assertIn("parent_8k_match.passed == true", self.runner)
        self.assertIn("quarantined-parent-8k-mismatch", self.runner)

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
        self.assertIn("tp4-mtp0", quality["baseline"])
        self.assertEqual(quality["baseline_sha256"], "2172c3bdba148062487ba73980fee46a5f1f2501baa37ceb83ca0e058bcaa83f")
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
            "port=19487", "--tensor-parallel-size 4", "--gpu-memory-utilization 0.60",
            "ZE_AFFINITY_MASK=0,1,2,3", "VLLM_XPU_ENABLE_XPU_GRAPH=0",
            "world_size=4, local_world_size=4", "rank_${rank}_0",
            "rank-cache-isolation-gate-failed", "strict_postcleanup", "trap cleanup_on_exit EXIT",
        ):
            self.assertIn(token, self.runner)

    def test_input_provenance_has_explicit_files_not_directories(self) -> None:
        self.assertIn('"$target_depth_root/depth-2048.json"', self.runner)
        self.assertIn('"$target_depth_root/depth-32768.json"', self.runner)
        self.assertIn('"$parent_verification"', self.runner)
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
