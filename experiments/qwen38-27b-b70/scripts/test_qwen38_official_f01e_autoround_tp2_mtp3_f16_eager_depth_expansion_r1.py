#!/usr/bin/env python3
"""Inert contract tests for the scoped current-f01e TP2/MTP3 depth expansion."""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import unittest


REPO = pathlib.Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp3-f16-eager-depth-expansion-r1-prereg.json"
RUNNER = LANE / "scripts/run-20260826-qwen38-official-f01e-autoround-tp2-mtp3-f16-eager-depth-expansion-r1.sh"
DEPTHS = [4096, 8192, 16384, 24576, 32768]


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.runner = RUNNER.read_text(encoding="utf-8")

    def test_exact_tp2_mtp3_identity(self) -> None:
        run = self.manifest["run_identity"]
        self.assertEqual((run["tensor_parallel"], run["mtp_depth"]), (2, 3))
        self.assertEqual(run["speculative_config"], {"method": "qwen3_next_mtp", "num_speculative_tokens": 3})
        self.assertEqual(run["startup_speculator_identity"], {"method": "mtp", "num_spec_tokens": 3})
        self.assertEqual(run["gpu_affinity"], "0,1")
        self.assertEqual(run["gpu_memory_utilization"], 0.6)
        self.assertEqual(run["graph_mode"], "off")
        self.assertEqual(run["kv_cache_dtype"], "float16")

    def test_2k_is_explicitly_excluded_from_execution(self) -> None:
        contract = self.manifest["exact_depth_contract"]
        self.assertEqual(contract["depths"], DEPTHS)
        self.assertEqual(set(contract["excluded_depths"]), {"2048"})
        self.assertIn("output token 90", contract["excluded_depths"]["2048"])
        self.assertIn("depths=(4096 8192 16384 24576 32768)", self.runner)
        self.assertIn("depths = [4096, 8192, 16384, 24576, 32768]", self.runner)
        self.assertNotIn("depths=(2048", self.runner)

    def test_same_topology_mtp0_target_is_frozen(self) -> None:
        target = self.manifest["target_oracles"]
        self.assertEqual(target["campaign"], "qwen38-official-f01e-autoround-tp2-mtp0-f16-eager-depth-expansion-20260826-r1")
        self.assertEqual(target["terminal_sha256"], "63fe2e8a85db47af331743b93b1c6e181f930775104f19483eb7b9e1da0f2c60")
        self.assertEqual(target["quality_sha256"], "ef15f39a848d262a4582b1ab6c9a2f10713ecfbcae02497bc4462c8ae5a3af96")
        self.assertEqual(set(target["depth_receipts"]), {"2048", *(str(depth) for depth in DEPTHS)})
        self.assertNotIn("autoround-tp1-", self.runner.lower())

    def test_mtp2_parent_terminal_arm_quality_are_pinned(self) -> None:
        parent = self.manifest["parent_oracles"]
        self.assertEqual(parent["campaign"], "qwen38-official-f01e-autoround-tp2-mtp2-f16-eager-depth-expansion-20260826-r1")
        self.assertEqual(parent["terminal_sha256"], "a803293e6273fc968161982f337c2962b64e99b2e8ff5a1ef3de7285895e5707")
        self.assertEqual(parent["arm_result_sha256"], "84ea935a30aa268752c16336b88e89f1926b8b68d9ccef62c6beddb2d966176f")
        self.assertEqual(parent["quality_sha256"], "df1c8a434d229f0b673f40fd8ee77cd659c953cdfaaaaf536c3191cf1903e1e9")
        self.assertEqual(set(parent["depth_receipts"]), {str(depth) for depth in DEPTHS})
        self.assertIn("frozen TP2/MTP2 five-valid-depth parent terminal failed", self.runner)
        self.assertIn("frozen TP2/MTP2 parent quality failed", self.runner)

    def test_parent_2k_divergence_is_exactly_bound(self) -> None:
        excluded = self.manifest["parent_oracles"]["excluded_depths"]["2048"]
        self.assertEqual(excluded["first_divergence"], {"zero_based": 89, "one_based": 90, "candidate": 59178, "target": 16539})
        self.assertEqual(excluded["depth_sha256"], "6f79f5461f3b933c90a54f7dfdf98e65a929f975051ba38729c2750277943d36")
        self.assertEqual(excluded["verification_sha256"], "f89773221b1837ea2bef1efd0dee1c484acb81acbf0aecd0c2194c8a6208affa")
        self.assertEqual(excluded["candidate_output_token_ids_sha256"], "921825efade0d24e902bdbaffecfde1275acf6afeb349d15f993f518b50f7446")
        self.assertEqual(excluded["target_output_token_ids_sha256"], "c606180877a26135511d7c4213c48c6107d20368e5d107aefe2b0de795ef4e89")
        for token in ("failed_or_quarantined_depths == [2048]", '"one_based":90', '"zero_based":89'):
            self.assertIn(token, self.runner)

    def test_five_parent_depth_and_verification_hashes_are_pinned(self) -> None:
        parent = self.manifest["parent_oracles"]
        self.assertTrue(all(row["drafted_tokens"] > 0 and 0 < row["accepted_tokens"] <= row["drafted_tokens"]
                            for row in parent["depth_receipts"].values()))
        for depth, row in parent["depth_receipts"].items():
            self.assertIn(f'parent_depth_root/depth-{depth}.json" {row["sha256"]}', self.runner)
            self.assertIn(f'parent_verify_root/depth-{depth}.json" {row["verification_sha256"]}', self.runner)
        self.assertIn("parent_depth_root/depth-2048.json", self.runner)
        self.assertIn("parent_verify_root/depth-2048.json", self.runner)

    def test_one_lifetime_and_isolated_acceptance_snapshots(self) -> None:
        self.assertIn('for depth in "${depths[@]}"', self.runner)
        body = self.runner.split('for depth in "${depths[@]}"', 1)[1]
        self.assertLess(body.index("depth-$depth.before.prom"), body.index('"$depth_helper" --execute'))
        self.assertLess(body.index('"$depth_helper" --execute'), body.index("depth-$depth.after.prom"))
        self.assertEqual(self.runner.count("dockerc run -d"), 1)
        for token in ("math.isfinite(value)", "a_draft >= b_draft", "a_accept >= b_accept",
                      "drafted > 0", "0 < accepted <= drafted", "candidate_ids == target_ids"):
            self.assertIn(token, self.runner)

    def test_quality_all16_and_target_baseline_are_required(self) -> None:
        quality = self.manifest["quality_contract"]
        self.assertIn("tp2-mtp0", quality["baseline"])
        match = re.search(r"quality_objective_gate\(\) \{\n  jq -e '(.*?)' \"\$1\"\n\}", self.runner, re.DOTALL)
        self.assertIsNotNone(match)
        usage = lambda value=0: {"prompt_tokens_details": {"cached_tokens": value}}
        payload = {"pass_all": True, "exact_cases": [{"usage": usage()} for _ in range(7)],
                   "repeat_case": {"runs": [{"usage": usage()} for _ in range(8)]},
                   "long_context_case": {"usage": usage()}}
        self.assertEqual(subprocess.run(["jq", "-e", match.group(1)], input=json.dumps(payload),
                                       text=True, capture_output=True).returncode, 0)
        payload["long_context_case"]["usage"] = usage(1)
        self.assertNotEqual(subprocess.run(["jq", "-e", match.group(1)], input=json.dumps(payload),
                                          text=True, capture_output=True).returncode, 0)
        self.assertIn("baseline_ok == 0", self.runner)

    def test_topology_cache_cleanup_and_fresh_identity(self) -> None:
        execution = self.manifest["execution"]
        self.assertEqual(execution["port"], 19495)
        self.assertIn("port=19495", self.runner)
        self.assertIn("--tensor-parallel-size 2", self.runner)
        self.assertIn("ZE_AFFINITY_MASK=0,1", self.runner)
        self.assertIn("world_size=2, local_world_size=2", self.runner)
        self.assertIn("rank_${rank}_0", self.runner)
        self.assertIn("strict_postcleanup", self.runner)
        self.assertIn("trap cleanup_on_exit EXIT", self.runner)

    def test_exact_completion_is_five_and_partial_retention_remains(self) -> None:
        self.assertIn("valid_depths == 5", self.runner)
        self.assertIn("valid_depths < 5", self.runner)
        self.assertIn("state=partial-depth-expansion", self.runner)
        self.assertIn('"per_depth_valid": rc == 0 and acceptance_ok and target_ok', self.runner)
        self.assertIn('if item["per_depth_valid"]', self.runner)

    def test_protected_values_and_default_inertness(self) -> None:
        interpretation = self.manifest["interpretation"]
        self.assertIsNone(interpretation["speed_floor"])
        self.assertEqual(interpretation["protected_decode_values_unchanged"],
                         [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144])
        self.assertFalse(interpretation["historical_replacement_allowed"])
        self.assertFalse(interpretation["site_publication_automatic"])
        self.assertFalse(interpretation["descendant_execution_authorized"])
        self.assertTrue(self.manifest["execution"]["default_is_inert"])
        self.assertIn("exact acknowledgement required", self.runner)


if __name__ == "__main__":
    unittest.main()
