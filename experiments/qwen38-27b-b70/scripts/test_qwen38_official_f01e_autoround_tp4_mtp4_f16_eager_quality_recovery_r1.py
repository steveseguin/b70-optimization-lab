#!/usr/bin/env python3
"""Inert contract tests for the focused current-f01e TP4/MTP4 quality recovery."""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest


REPO = pathlib.Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-26-qwen38-official-f01e-autoround-tp4-mtp4-f16-eager-quality-recovery-r1-prereg.json"
RUNNER = LANE / "scripts/run-20260826-qwen38-official-f01e-autoround-tp4-mtp4-f16-eager-quality-recovery-r1.sh"
NOTE = LANE / "notes/2026-08-26-qwen38-official-f01e-autoround-tp4-mtp4-f16-eager-quality-recovery-r1-preregistration.md"
DEPTHS = [4096, 8192, 16384, 24576]
PUBLISHABLE = [4096, 16384, 24576]


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text())
        cls.runner = RUNNER.read_text()
        cls.note = NOTE.read_text()

    def test_exact_identity_and_fresh_recovery_roots(self) -> None:
        run = self.manifest["run_identity"]
        self.assertEqual((run["tensor_parallel"], run["mtp_depth"]), (4, 4))
        self.assertEqual(run["speculative_config"], {"method": "qwen3_next_mtp", "num_speculative_tokens": 4})
        self.assertEqual(run["startup_speculator_identity"], {"method": "mtp", "num_spec_tokens": 4})
        self.assertEqual((run["gpu_affinity"], run["gpu_memory_utilization"], run["graph_mode"], run["kv_cache_dtype"]), ("0,1,2,3", 0.6, "off", "float16"))
        execution = self.manifest["execution"]
        self.assertEqual(execution["port"], 19491)
        self.assertIn("quality-recovery", execution["output_root"])
        self.assertIn("quality-recovery", execution["cache_root"])
        self.assertTrue(execution["default_is_inert"])
        self.assertIn("port=19491", self.runner)
        self.assertIn("q38-f01e-ar-tp4-mtp4-f16-recovery-r1", self.runner)

    def test_only_recovery_depths_are_requested(self) -> None:
        contract = self.manifest["exact_depth_contract"]
        self.assertEqual(contract["depths"], DEPTHS)
        self.assertEqual(contract["target_parity_depths"], PUBLISHABLE)
        self.assertEqual(contract["parent_reproduction_only_depths"], [8192])
        self.assertEqual(contract["explicitly_excluded_depths"], [2048, 32768])
        self.assertIn("depths=(4096 8192 16384 24576)", self.runner)
        self.assertNotIn("depths=(2048", self.runner)
        self.assertNotIn('"$target_depth_root/depth-2048.json"', self.runner)
        self.assertNotIn('"$target_depth_root/depth-32768.json"', self.runner)
        self.assertIn("does not request 2K or 32K", self.note.replace("\n", " "))
        self.assertIn("excluded_from_recovery == [2048,32768]", self.runner)

    def test_target_oracles_and_8k_parent_are_narrow(self) -> None:
        targets = self.manifest["target_oracles"]["depth_receipts"]
        self.assertEqual(list(targets), ["4096", "8192", "16384", "24576"])
        self.assertEqual(targets["4096"]["sha256"], "1dbba43c7ed816156f53b489e2287247e8a96f26a7d5f15a1a381d28f7e89e02")
        self.assertEqual(targets["16384"]["sha256"], "d0a621857ecd56e7b2cb44ec07381b5e4ebfbd3e0df322fdc741f92f0715481a")
        self.assertEqual(targets["24576"]["sha256"], "13122dd794bd0e9106450224b5a19261585a2740a9b293e787e8e6a74e4fd4b6")
        parent = self.manifest["parent_sentinel"]
        self.assertEqual(parent["state"], "quarantined-target-parity-failed")
        self.assertFalse(parent["target_parity"])
        self.assertEqual(parent["output_token_ids_sha256"], "dd31856f45269d222efe0f6f5f1ac9342b6c9ae55e5ce9129fc02b27abdb7e8e")
        self.assertIn("parent_8k_match.passed == true", self.runner)
        self.assertIn('"candidate":411,"one_based":99,"target":579', self.runner)

    def test_prior_engine_fatal_is_frozen_and_not_called_quality_mismatch(self) -> None:
        prior = self.manifest["prior_failure"]
        self.assertEqual(prior["excluded_depths"], [2048, 32768])
        self.assertEqual(prior["observed_32k_target_prefix_tokens"], 126)
        self.assertIn("Expected spec_token == num_spec_decodes", prior["fatal_error"])
        self.assertEqual(prior["classification"], "incomplete-mixed-depth-engine-fatal-32k-quality-not-run")
        for digest in (prior["terminal_sha256"], prior["arm_sha256"], prior["quality_stdout_sha256"], prior["server_log_sha256"]):
            self.assertIn(digest, self.runner)
        self.assertIn("quality battery", self.note)
        self.assertIn("not an observed model-quality mismatch", self.note)

    def test_one_server_lifetime_order_and_isolated_acceptance(self) -> None:
        self.assertEqual(self.runner.count("dockerc run -d"), 1)
        self.assertIn('for depth in "${depths[@]}"', self.runner)
        loop = self.runner.split('for depth in "${depths[@]}"', 1)[1]
        self.assertLess(loop.index("depth-$depth.before.prom"), loop.index('"$depth_helper" --execute'))
        self.assertLess(loop.index('"$depth_helper" --execute'), loop.index("depth-$depth.after.prom"))
        self.assertLess(self.runner.index('for depth in "${depths[@]}"'), self.runner.index('"$quality_helper" --base-url'))
        for token in ("math.isfinite(value)", "a_draft >= b_draft", "a_accept >= b_accept", "drafted > 0", "0 < accepted <= drafted"):
            self.assertIn(token, self.runner)

    def test_success_freezes_only_three_grade_c_depths(self) -> None:
        block = self.runner.split("write_arm_result()", 1)[1].split("terminal_receipt()", 1)[0]
        script = block.split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            (root / "exact-depth").mkdir()
            (root / "verification").mkdir()
            for depth in DEPTHS:
                (root / "exact-depth" / f"depth-{depth}.rc").write_text("0\n")
                (root / "verification" / f"depth-{depth}.json").write_text(json.dumps({
                    "acceptance": {"passed": True},
                    "same_topology_target_verification": {"passed": depth != 8192},
                }))
            output = root / "arm-result.json"
            subprocess.run([
                sys.executable, "-c", script, str(output),
                "passed-quality-clean-recovery", "synthetic-success",
                "4", "4", "3", "0", "1", "0", "1", "1", "1", "1", "1", "1", str(root),
            ], check=True)
            arm = json.loads(output.read_text())
            self.assertEqual(arm["frozen_same_topology_oracle_depths"], PUBLISHABLE)
            self.assertEqual(arm["human_grade_c_publication_depths"], PUBLISHABLE)
            self.assertEqual(arm["failed_or_quarantined_depths"], [8192])
            self.assertFalse(arm["automatic_publication_allowed"])
            self.assertEqual(arm["excluded_from_recovery"], [2048, 32768])
            subprocess.run([
                sys.executable, "-c", script, str(output),
                "quarantined-quality-failed", "synthetic-failure",
                "4", "4", "3", "1", "1", "40", "1", "1", "1", "1", "0", "0", str(root),
            ], check=True)
            self.assertEqual(json.loads(output.read_text())["frozen_same_topology_oracle_depths"], [])

    def test_success_and_fail_closed_state_logic(self) -> None:
        self.assertIn("passed_depths == 4 && acceptance_passes == 4 && target_passes == 3 && valid_depths == 3", self.runner)
        self.assertIn("state=passed-quality-clean-recovery", self.runner)
        self.assertIn("runner_rc=0", self.runner)
        self.assertIn("state=quarantined-recovery-cell-failed", self.runner)
        self.assertIn("quarantined-parent-8k-mismatch", self.runner)
        self.assertIn("quarantined-quality-failed", self.runner)

    def test_full_quality_cache_topology_and_cleanup_remain_mandatory(self) -> None:
        quality = self.manifest["quality_contract"]
        self.assertEqual(quality["baseline_sha256"], "2172c3bdba148062487ba73980fee46a5f1f2501baa37ceb83ca0e058bcaa83f")
        match = re.search(
            r"""quality_objective_gate\(\) \{\n  jq -e '(.*?)' "\$1"\n\}""",
            self.runner,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        jq_filter = match.group(1)
        usage = lambda: {"prompt_tokens_details": {"cached_tokens": 0}}
        payload = {"pass_all": True, "exact_cases": [{"usage": usage()} for _ in range(7)],
                   "repeat_case": {"runs": [{"usage": usage()} for _ in range(8)]},
                   "long_context_case": {"usage": usage()}}
        self.assertEqual(subprocess.run(["jq", "-e", jq_filter], input=json.dumps(payload), text=True, capture_output=True).returncode, 0)
        self.assertIn(".baseline_match_all == true", self.runner)
        for token in ("world_size=4, local_world_size=4", "rank_${rank}_0", "rank-cache-isolation-gate-failed", "strict_postcleanup", "trap cleanup_on_exit EXIT"):
            self.assertIn(token, self.runner)

    def test_authority_is_narrow_and_protected_values_stay_fixed(self) -> None:
        interpretation = self.manifest["interpretation"]
        self.assertEqual(interpretation["successful_human_grade_c_depths"], PUBLISHABLE)
        self.assertEqual(interpretation["retained_prior_quarantined_depths"], [2048, 8192])
        self.assertEqual(interpretation["retained_prior_runtime_fatal_depths"], [32768])
        self.assertEqual(interpretation["protected_decode_values_unchanged"], [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144])
        self.assertFalse(interpretation["site_publication_automatic"])
        self.assertFalse(interpretation["historical_replacement_allowed"])
        self.assertFalse(interpretation["existing_tp4_8k_replacement_allowed"])
        self.assertTrue(interpretation["x0_missing"])
        self.assertIn("No diagnostic speed", self.note)

    def test_runner_is_inert_and_syntax_clean(self) -> None:
        self.assertEqual(subprocess.run(["bash", "-n", str(RUNNER)]).returncode, 0)
        self.assertIn("exact acknowledgement required", self.runner)
        self.assertIn("require_clean_pushed_main", self.runner)
        self.assertIn("require_idle", self.runner)
        self.assertIn("fresh campaign roots", self.runner)


if __name__ == "__main__":
    unittest.main()
