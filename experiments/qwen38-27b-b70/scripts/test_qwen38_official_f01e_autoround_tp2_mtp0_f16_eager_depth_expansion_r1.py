#!/usr/bin/env python3
"""Inert contract tests for the current-f01e TP2/MTP0 depth expansion."""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp0-f16-eager-depth-expansion-r1-prereg.json"
NOTE = LANE / "notes/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp0-f16-eager-depth-expansion-r1-preregistration.md"
RUNNER = LANE / "scripts/run-20260826-qwen38-official-f01e-autoround-tp2-mtp0-f16-eager-depth-expansion-r1.sh"
DEPTHS = [2048, 4096, 8192, 16384, 24576, 32768]


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text())
        cls.note = NOTE.read_text()
        cls.runner = RUNNER.read_text()

    def test_current_image_target_only_tp2_identity(self) -> None:
        run = self.manifest["run_identity"]
        self.assertEqual((run["tensor_parallel"], run["mtp_depth"]), (2, 0))
        self.assertEqual(run["gpu_affinity"], "0,1")
        self.assertEqual(run["gpu_memory_utilization"], 0.6)
        self.assertEqual(run["graph_mode"], "off")
        self.assertEqual(run["kv_cache_dtype"], "float16")
        self.assertIsNone(run["speculative_config"])
        self.assertIn("--tensor-parallel-size 2", self.runner)
        self.assertNotIn("--speculative-config", self.runner)
        self.assertNotIn("num_spec_tokens", self.runner)
        self.assertNotIn("--kv-cache-dtype", self.runner)

    def test_six_exact_depths_share_one_server_lifetime(self) -> None:
        self.assertEqual(self.manifest["exact_depth_contract"]["depths"], DEPTHS)
        self.assertIn("depths=(2048 4096 8192 16384 24576 32768)", self.runner)
        self.assertIn('for depth in "${depths[@]}"', self.runner)
        self.assertIn("depth-$depth.rc", self.runner)
        self.assertEqual(self.runner.count("dockerc run -d"), 1)
        self.assertTrue(self.manifest["execution"]["one_server_lifetime"])

    def test_no_same_image_tp2_parent_is_fabricated(self) -> None:
        prior = self.manifest["prior_evidence"]
        self.assertFalse(prior["same_image_same_topology_parent_available"])
        self.assertIn("No current-f01e", prior["current_image_gap"])
        self.assertNotIn("parent_8k", self.runner)
        self.assertNotIn("parent_terminal", self.runner)
        self.assertIn("There is no same-image TP2", self.note)

    def test_cross_topology_comparisons_are_caveats(self) -> None:
        interpretation = self.manifest["interpretation"]
        self.assertTrue(interpretation["cross_topology_mismatch_is_caveat_not_rejection"])
        self.assertIn("comparison caveat only; mismatch does not reject", self.runner)
        self.assertIn("passed-quality-clean-depth-expansion-with-comparison-caveat", self.runner)
        self.assertIn("passed_depths == 6 && objective_quality_ok == 1 && topology_ok == 1", self.runner)
        self.assertIn("qwen38-official-f01e-autoround-tp4-mtp0-f16-eager-depth-expansion-20260826-r1/quality.json", self.runner)
        for depth in DEPTHS:
            self.assertIn(f'"$tp1_target_root/depth-{depth}.json"', self.runner)

    def _run_arm_writer(self, state: str, *, failed_depth: int | None = None, objective: str = "1", baseline: str = "0") -> dict:
        match = re.search(r"write_arm_result\(\) \{.*?<<'PY'\n(.*?)\nPY\n\}", self.runner, re.DOTALL)
        self.assertIsNotNone(match)
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "exact-depth").mkdir()
            for depth in DEPTHS:
                (root / "exact-depth" / f"depth-{depth}.rc").write_text("1\n" if depth == failed_depth else "0\n")
            output = root / "arm-result.json"
            args = [
                str(output), state, "synthetic-test", str(5 if failed_depth else 6), "0", "1",
                "1", "0", "1", "1", "1", objective, baseline, str(root),
            ]
            completed = subprocess.run(["python3", "-c", match.group(1), *args], text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            return json.loads(output.read_text())

    def test_comparison_caveat_does_not_suppress_tp2_native_oracles(self) -> None:
        result = self._run_arm_writer("passed-quality-clean-depth-expansion-with-comparison-caveat")
        self.assertEqual(result["frozen_same_topology_oracle_depths"], DEPTHS)
        self.assertTrue(result["per_depth_descendant_oracle_authority"])
        self.assertFalse(result["tp4_quality_comparison_passed"])

    def test_partial_native_depths_are_retained_independently(self) -> None:
        result = self._run_arm_writer("partial-depth-expansion", failed_depth=2048)
        self.assertEqual(result["frozen_same_topology_oracle_depths"], DEPTHS[1:])
        self.assertEqual(result["failed_or_quarantined_depths"], [2048])
        self.assertTrue(result["per_depth_descendant_oracle_authority"])

    def test_failed_or_objective_bad_state_cannot_freeze(self) -> None:
        failed = self._run_arm_writer("failed")
        bad_quality = self._run_arm_writer("partial-depth-expansion", failed_depth=2048, objective="0")
        self.assertEqual(failed["frozen_same_topology_oracle_depths"], [])
        self.assertEqual(bad_quality["frozen_same_topology_oracle_depths"], [])
        self.assertFalse(failed["per_depth_descendant_oracle_authority"])
        self.assertFalse(bad_quality["per_depth_descendant_oracle_authority"])

    def test_objective_quality_requires_all_sixteen_cache_zero_records(self) -> None:
        match = re.search(r"quality_objective_gate\(\) \{\n  jq -e '(.*?)' \"\$1\"\n\}", self.runner, re.DOTALL)
        self.assertIsNotNone(match)
        jq_filter = match.group(1)
        usage = lambda value=0: {"prompt_tokens_details": {"cached_tokens": value}}
        payload = {
            "pass_all": True,
            "exact_cases": [{"usage": usage()} for _ in range(7)],
            "repeat_case": {"runs": [{"usage": usage()} for _ in range(8)]},
            "long_context_case": {"usage": usage()},
        }
        ok = subprocess.run(["jq", "-e", jq_filter], input=json.dumps(payload), text=True, capture_output=True)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        payload["long_context_case"]["usage"] = usage(1)
        cached = subprocess.run(["jq", "-e", jq_filter], input=json.dumps(payload), text=True, capture_output=True)
        self.assertNotEqual(cached.returncode, 0)
        del payload["long_context_case"]["usage"]["prompt_tokens_details"]["cached_tokens"]
        missing = subprocess.run(["jq", "-e", jq_filter], input=json.dumps(payload), text=True, capture_output=True)
        self.assertNotEqual(missing.returncode, 0)

    def test_tp2_topology_cache_and_cleanup_fail_closed(self) -> None:
        for token in (
            "ZE_AFFINITY_MASK=0,1",
            "VLLM_XPU_ENABLE_XPU_GRAPH=0",
            "--enforce-eager",
            "world_size=2, local_world_size=2",
            "for rank in 0 1; do",
            "rank_${rank}_0",
            "strict_postcleanup",
        ):
            self.assertIn(token, self.runner)
        self.assertNotIn("ZE_AFFINITY_MASK=0,1,2,3", self.runner)
        self.assertNotIn("ONEAPI_DEVICE_SELECTOR", self.runner)

    def test_depth_zero_is_explicitly_missing(self) -> None:
        contract = self.manifest["exact_depth_contract"]
        self.assertEqual(contract["depth_zero_state"], "missing")
        self.assertNotIn(0, contract["depths"])
        self.assertIn("Context zero remains explicitly missing", self.note)

    def test_protected_values_and_routes_are_immutable(self) -> None:
        interpretation = self.manifest["interpretation"]
        self.assertFalse(interpretation["historical_replacement_allowed"])
        self.assertFalse(interpretation["protected_route_replacement_allowed"])
        self.assertFalse(interpretation["older_tp2_replacement_allowed"])
        self.assertFalse(interpretation["automatic_publication_allowed"])
        self.assertEqual(
            interpretation["protected_decode_values_unchanged"],
            [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144],
        )
        self.assertIsNone(interpretation["speed_floor"])

    def test_launch_is_inert_and_fresh(self) -> None:
        execution = self.manifest["execution"]
        self.assertTrue(execution["default_is_inert"])
        self.assertTrue(execution["fresh_roots_only"])
        self.assertEqual(execution["port"], 19492)
        self.assertIn("exact acknowledgement required", self.runner)
        self.assertIn("[[ ! -e \"$root\" ]]", self.runner)
        self.assertIn("[[ ! -e \"$cache_root\" ]]", self.runner)


if __name__ == "__main__":
    unittest.main()
