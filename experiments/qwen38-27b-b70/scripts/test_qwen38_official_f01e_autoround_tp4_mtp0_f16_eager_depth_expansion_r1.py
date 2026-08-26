#!/usr/bin/env python3
"""Inert contract tests for the current-f01e TP4/MTP0 depth expansion."""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-26-qwen38-official-f01e-autoround-tp4-mtp0-f16-eager-depth-expansion-r1-prereg.json"
RUNNER = LANE / "scripts/run-20260826-qwen38-official-f01e-autoround-tp4-mtp0-f16-eager-depth-expansion-r1.sh"
DEPTHS = [2048, 4096, 8192, 16384, 24576, 32768]


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text())
        cls.runner = RUNNER.read_text()

    def test_exact_target_only_identity(self) -> None:
        run = self.manifest["run_identity"]
        self.assertEqual((run["tensor_parallel"], run["mtp_depth"]), (4, 0))
        self.assertEqual(run["gpu_affinity"], "0,1,2,3")
        self.assertEqual(run["gpu_memory_utilization"], 0.6)
        self.assertEqual(run["graph_mode"], "off")
        self.assertIsNone(run["speculative_config"])
        self.assertNotIn("--speculative-config", self.runner)
        self.assertNotIn("num_spec_tokens", self.runner)

    def test_six_depths_one_server_lifetime(self) -> None:
        self.assertEqual(self.manifest["exact_depth_contract"]["depths"], DEPTHS)
        self.assertIn("depths=(2048 4096 8192 16384 24576 32768)", self.runner)
        self.assertIn('for depth in "${depths[@]}"', self.runner)
        self.assertIn('depth-$depth.rc', self.runner)
        self.assertEqual(self.runner.count("dockerc run -d"), 1)
        self.assertTrue(self.manifest["execution"]["one_server_lifetime"])

    def test_tp4_parent_8k_is_a_hard_gate(self) -> None:
        parent = self.manifest["parent_oracle"]
        self.assertEqual(parent["exact_8k_sha256"], "49ea5caae577dae86bb52378e84a6ad45da051ae403904158751903393121d9e")
        self.assertIn('depth == 8192', self.runner)
        self.assertIn('parent_8k_match.passed == true', self.runner)
        self.assertIn("quarantined-parent-8k-mismatch", self.runner)

    def test_tp1_comparisons_are_caveats_only(self) -> None:
        self.assertTrue(self.manifest["interpretation"]["cross_topology_mismatch_is_caveat_not_rejection"])
        self.assertIn("comparison caveat only; mismatch does not reject", self.runner)
        self.assertIn("passed-quality-clean-depth-expansion-with-comparison-caveat", self.runner)
        self.assertIn("comparison_passes == 6", self.runner)
        self.assertIn("passed_depths == 6 && objective_quality_ok == 1 && topology_ok == 1", self.runner)
        self.assertNotIn('"$quality_helper" "$quality_baseline" "$tp1_target_root"', self.runner)
        for depth in DEPTHS:
            self.assertIn(f'"$tp1_target_root/depth-{depth}.json"', self.runner)

    def test_partial_receipts_are_retained_and_independently_frozen(self) -> None:
        for token in (
            '"depth_receipts": receipts',
            '"failed_or_quarantined_depths"',
            'if item["exact_passed"]',
            'state=partial-depth-expansion',
            'per_depth_descendant_oracle_authority',
        ):
            self.assertIn(token, self.runner)

    def test_generic_failed_state_cannot_freeze_even_with_true_native_flags(self) -> None:
        match = re.search(r"write_arm_result\(\) \{.*?<<'PY'\n(.*?)\nPY\n\}", self.runner, re.DOTALL)
        self.assertIsNotNone(match)
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "exact-depth").mkdir()
            for depth in DEPTHS:
                (root / "exact-depth" / f"depth-{depth}.rc").write_text("0\n")
            output = root / "arm-result.json"
            args = [str(output), "failed", "synthetic-infrastructure-failure", "6", "6", "0", "1", "34", "1", "1", "1", "1", "1", "1", str(root)]
            completed = subprocess.run(["python3", "-c", match.group(1), *args], text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(output.read_text())
            self.assertEqual(result["frozen_same_topology_oracle_depths"], [])
            self.assertFalse(result["per_depth_descendant_oracle_authority"])

    def test_quality_requires_all_sixteen_cache_zero_records(self) -> None:
        match = re.search(r"quality_objective_gate\(\) \{\n  jq -e '(.*?)' \"\$1\"\n\}", self.runner, re.DOTALL)
        self.assertIsNotNone(match)
        jq_filter = match.group(1)
        usage = lambda value=0: {"prompt_tokens_details": {"cached_tokens": value}}
        payload = {"pass_all": True, "exact_cases": [{"usage": usage()} for _ in range(7)], "repeat_case": {"runs": [{"usage": usage()} for _ in range(8)]}, "long_context_case": {"usage": usage()}}
        ok = subprocess.run(["jq", "-e", jq_filter], input=json.dumps(payload), text=True, capture_output=True)
        self.assertEqual(ok.returncode, 0)
        payload["long_context_case"]["usage"] = usage(1)
        bad = subprocess.run(["jq", "-e", jq_filter], input=json.dumps(payload), text=True, capture_output=True)
        self.assertNotEqual(bad.returncode, 0)

    def test_topology_cache_and_cleanup_are_fail_closed(self) -> None:
        for token in ("ZE_AFFINITY_MASK=0,1,2,3", "VLLM_XPU_ENABLE_XPU_GRAPH=0", "--enforce-eager", "world_size=4, local_world_size=4", "rank_${rank}_0", "strict_postcleanup"):
            self.assertIn(token, self.runner)
        self.assertNotIn("ONEAPI_DEVICE_SELECTOR", self.runner)

    def test_no_replacement_and_inert_ack(self) -> None:
        interpretation = self.manifest["interpretation"]
        self.assertFalse(interpretation["historical_replacement_allowed"])
        self.assertFalse(interpretation["protected_route_replacement_allowed"])
        self.assertFalse(interpretation["existing_tp4_8k_replacement_allowed"])
        self.assertEqual(interpretation["protected_decode_values_unchanged"], [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144])
        self.assertTrue(self.manifest["execution"]["default_is_inert"])
        self.assertIn("exact acknowledgement required", self.runner)
        self.assertIn("port=19486", self.runner)


if __name__ == "__main__":
    unittest.main()
