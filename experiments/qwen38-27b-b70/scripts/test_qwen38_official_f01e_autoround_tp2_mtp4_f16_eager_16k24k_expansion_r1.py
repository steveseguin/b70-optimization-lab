#!/usr/bin/env python3
"""Inert contract tests for the bounded TP2/MTP4 16K+24K expansion."""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import unittest


REPO = pathlib.Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-16k24k-expansion-r1-prereg.json"
RUNNER = LANE / "scripts/run-20260826-qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-16k24k-expansion-r1.sh"
DEPTHS = [16384, 24576]
EXCLUDED = [0, 2048, 4096, 8192, 32768]


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.runner = RUNNER.read_text(encoding="utf-8")

    def test_exact_tp2_mtp4_eager_identity(self) -> None:
        run = self.manifest["run_identity"]
        self.assertEqual((run["tensor_parallel"], run["mtp_depth"]), (2, 4))
        self.assertEqual(run["speculative_config"], {"method": "qwen3_next_mtp", "num_speculative_tokens": 4})
        self.assertEqual(run["startup_speculator_identity"], {"method": "mtp", "num_spec_tokens": 4})
        self.assertEqual((run["graph_mode"], run["kv_cache_dtype"]), ("off", "float16"))
        self.assertEqual((run["gpu_affinity"], run["gpu_memory_utilization"]), ("0,1", 0.6))

    def test_scope_is_exactly_16k_and_24k(self) -> None:
        contract = self.manifest["exact_depth_contract"]
        self.assertEqual(contract["depths"], DEPTHS)
        self.assertEqual(contract["excluded_depths"], EXCLUDED)
        self.assertIn("depths=(16384 24576)", self.runner)
        self.assertIn("depths = [16384, 24576]", self.runner)
        self.assertNotRegex(self.runner, r"depths=\([^)]*(?:2048|4096|8192|32768)")
        self.assertIn("valid_depths == 2", self.runner)
        self.assertIn("valid_depths < 2", self.runner)

    def test_passed_4k_gate_is_frozen_without_auto_authority(self) -> None:
        gate = self.manifest["passed_4k_gate"]
        self.assertEqual(gate["terminal_sha256"], "0dae257d3a1cafad3dd16c966823a5db1122fb6c811fa28a5cf466cc0c8b902d")
        self.assertEqual((gate["accepted_tokens"], gate["drafted_tokens"]), (90, 148))
        for key in ("terminal_sha256", "arm_result_sha256", "quality_sha256", "verification_sha256", "exact_4k_sha256"):
            self.assertIn(gate[key], self.runner)
        self.assertIn(".arm.depth_expansion_authorized == false", self.runner)

    def test_same_topology_mtp0_targets_are_exactly_two(self) -> None:
        target = self.manifest["target_oracles"]
        self.assertEqual(set(target["depth_receipts"]), {"16384", "24576"})
        for depth, row in target["depth_receipts"].items():
            self.assertIn(f'target_depth_root/depth-{depth}.json" {row["sha256"]}', self.runner)
        self.assertNotIn("autoround-tp1-", self.runner.lower())
        self.assertNotIn("autoround-tp4-mtp0", self.runner.lower())

    def test_tp2_mtp3_parent_two_depth_receipts_are_pinned(self) -> None:
        parent = self.manifest["mtp3_parent"]
        self.assertEqual(parent["terminal_sha256"], "977a0aba4fed5510fb8ec568e3a9eb99df4f86a872478878e8c85d147899b64c")
        self.assertEqual(set(parent["depth_receipts"]), {"16384", "24576"})
        for depth, row in parent["depth_receipts"].items():
            self.assertGreater(row["drafted_tokens"], 0)
            self.assertGreater(row["accepted_tokens"], 0)
            self.assertLessEqual(row["accepted_tokens"], row["drafted_tokens"])
            self.assertIn(f'parent_depth_root/depth-{depth}.json" {row["sha256"]}', self.runner)
            self.assertIn(f'parent_verify_root/depth-{depth}.json" {row["verification_sha256"]}', self.runner)
        self.assertIn("frozen TP2/MTP3 16K/24K parent terminal failed", self.runner)

    def test_each_request_has_isolated_positive_conserved_acceptance(self) -> None:
        self.assertIn('for depth in "${depths[@]}"', self.runner)
        body = self.runner.split('for depth in "${depths[@]}"', 1)[1]
        self.assertLess(body.index("depth-$depth.before.prom"), body.index('"$depth_helper" --execute'))
        self.assertLess(body.index('"$depth_helper" --execute'), body.index("depth-$depth.after.prom"))
        for token in ("math.isfinite(value)", "a_draft >= b_draft", "a_accept >= b_accept", "drafted > 0", "0 < accepted <= drafted", "candidate_ids == target_ids"):
            self.assertIn(token, self.runner)

    def test_quality_baseline_and_all_cache_zero_are_required(self) -> None:
        self.assertEqual(self.manifest["quality_contract"]["baseline_sha256"], "ef15f39a848d262a4582b1ab6c9a2f10713ecfbcae02497bc4462c8ae5a3af96")
        match = re.search(r"quality_objective_gate\(\) \{\n  jq -e '(.*?)' \"\$1\"\n\}", self.runner, re.DOTALL)
        self.assertIsNotNone(match)
        usage = lambda cached=0: {"prompt_tokens_details": {"cached_tokens": cached}}
        payload = {"pass_all": True, "exact_cases": [{"usage": usage()} for _ in range(7)], "repeat_case": {"runs": [{"usage": usage()} for _ in range(8)]}, "long_context_case": {"usage": usage()}}
        self.assertEqual(subprocess.run(["jq", "-e", match.group(1)], input=json.dumps(payload), text=True, capture_output=True).returncode, 0)
        payload["long_context_case"]["usage"] = usage(1)
        self.assertNotEqual(subprocess.run(["jq", "-e", match.group(1)], input=json.dumps(payload), text=True, capture_output=True).returncode, 0)
        self.assertIn("baseline_ok == 0", self.runner)

    def test_tp2_topology_rank_cache_model_cleanup_and_fresh_roots(self) -> None:
        execution = self.manifest["execution"]
        self.assertEqual(execution["port"], 19522)
        for token in ("--tensor-parallel-size 2", "ZE_AFFINITY_MASK=0,1", "world_size=2, local_world_size=2", "rank_${rank}_0", "model-verification.json", "strict_postcleanup", "trap cleanup_on_exit EXIT"):
            self.assertIn(token, self.runner)
        self.assertEqual(self.runner.count("dockerc run -d"), 1)
        self.assertIn('[[ ! -e "$root" ]]', self.runner)
        self.assertIn('[[ ! -e "$cache_root" ]]', self.runner)

    def test_execute_requires_clean_pushed_main(self) -> None:
        self.assertTrue(self.manifest["execution"]["clean_pushed_main_required"])
        for token in ("repository must be on main", "repository must be clean", "local main must equal cached origin/main", "local main must equal live origin/main", "git -C \"$repo\" ls-remote"):
            self.assertIn(token, self.runner)

    def test_no_auto_publication_replacement_or_other_depth(self) -> None:
        interpretation = self.manifest["interpretation"]
        self.assertIsNone(interpretation["speed_floor"])
        for key in ("historical_replacement_allowed", "protected_route_replacement_allowed", "site_publication_automatic", "other_depth_expansion_authorized", "descendant_execution_authorized"):
            self.assertFalse(interpretation[key])
        self.assertIn('"complete_descendant_expansion_authorized": False', self.runner)
        self.assertIn('"automatic_descendant_expansion": False', self.runner)
        self.assertIn("exact acknowledgement required", self.runner)
        self.assertTrue(self.manifest["execution"]["default_is_inert"])

    def test_protected_values_unchanged(self) -> None:
        self.assertEqual(self.manifest["interpretation"]["protected_decode_values_unchanged"], [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144])


if __name__ == "__main__":
    unittest.main()
