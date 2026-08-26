#!/usr/bin/env python3
"""Inert tests for the current-f01e AutoRound TP4/MTP0 oracle sentinel."""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import unittest


REPO = pathlib.Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-26-qwen38-official-f01e-autoround-tp4-mtp0-f16-eager-8k-oracle-sentinel-r1-prereg.json"
RUNNER = LANE / "scripts/run-20260826-qwen38-official-f01e-autoround-tp4-mtp0-f16-eager-8k-oracle-sentinel-r1.sh"


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.runner = RUNNER.read_text(encoding="utf-8")

    def test_exact_tp4_mtp0_f16_eager_identity(self) -> None:
        run = self.manifest["run_identity"]
        self.assertEqual(run["tensor_parallel"], 4)
        self.assertEqual(run["mtp_depth"], 0)
        self.assertEqual(run["kv_cache_dtype"], "float16")
        self.assertEqual(run["graph_mode"], "off")
        self.assertEqual(run["gpu_affinity"], "0,1,2,3")
        self.assertLessEqual(run["gpu_memory_utilization"], 0.60)
        self.assertEqual(run["max_num_seqs"], 1)
        self.assertEqual(run["max_model_len"], 32896)
        self.assertEqual(self.manifest["exact_depth_contract"]["depths"], [8192])

    def test_target_only_server_has_no_speculative_binding(self) -> None:
        self.assertIsNone(self.manifest["run_identity"]["speculative_config"])
        self.assertTrue(self.manifest["target_only_contract"]["speculative_config_absent"])
        self.assertIn("--tensor-parallel-size 4", self.runner)
        self.assertIn("served_model=qwen38-official-f01e-autoround-tp4-mtp0", self.runner)
        self.assertIn('--served-model-name "$served_model"', self.runner)
        self.assertNotIn("--speculative-config", self.runner)
        self.assertNotIn("num_spec_tokens", self.runner)
        self.assertNotIn("num_speculative_tokens", self.runner)
        self.assertNotIn("acceptance", self.runner.lower())
        self.assertIn("speculative_config=SpeculativeConfig", self.runner)
        self.assertIn("quantization=inc", self.runner)

    def test_graph_off_f16_and_four_card_selection_are_exact(self) -> None:
        for token in (
            "--enforce-eager",
            "--gpu-memory-utilization 0.60",
            "--max-num-seqs 1",
            "--max-model-len 32896",
            "ZE_AFFINITY_MASK=0,1,2,3",
            "VLLM_XPU_ENABLE_XPU_GRAPH=0",
            "VLLM_XPU_GRAPH=0",
            "kv_cache_dtype=auto",
        ):
            self.assertIn(token, self.runner)
        self.assertNotIn("--kv-cache-dtype", self.runner)
        self.assertNotIn("ONEAPI_DEVICE_SELECTOR", self.runner)

    def test_all_four_workers_are_startup_gated(self) -> None:
        self.assertIn("world_size=4, local_world_size=4", self.runner)
        self.assertIn("for rank in 0 1 2 3", self.runner)
        self.assertIn('world_size=4 rank=$rank local_rank=$rank', self.runner)
        self.assertIn("tp4-worker-topology-gate-failed", self.runner)

    def test_cross_topology_oracle_is_pinned_not_inferred(self) -> None:
        oracle = self.manifest["exact_depth_contract"]["target_oracle"]
        self.assertEqual(
            oracle["sha256"],
            "94f7d11862b2e35b057e7a95b3d529b89a4c2857d8886ce93e4b4d85b7385c34",
        )
        self.assertEqual(
            oracle["output_token_ids_sha256"],
            "34e792ccf3c1d795b686750f27990de2ca605c22046c97b3fff8ad0a7fc82e53",
        )
        self.assertIn("conservative same-image cross-topology comparison", oracle["gate"])
        self.assertIn("candidate_ids == target_ids", self.runner)
        self.assertIn("separate same-topology TP4 oracle", self.manifest["purpose"])

    def test_objective_quality_is_required_and_comparisons_are_separate(self) -> None:
        self.assertIn("--require-baseline", self.runner)
        self.assertIn("--repeat-runs 8", self.runner)
        self.assertIn("--long-context-tokens 8192", self.runner)
        self.assertIn('($q.pass_all == true)', self.runner)
        self.assertIn("quality_objective_gate \"$root/quality.json\"", self.runner)
        self.assertIn("jq -e '.baseline_match_all == true'", self.runner)
        self.assertIn(
            "depth_rc == 0 && objective_quality_ok == 1 && topology_ok == 1 && target_ok == 1 && baseline_ok == 1",
            self.runner,
        )
        self.assertIn(
            "depth_rc == 0 && objective_quality_ok == 1 && topology_ok == 1",
            self.runner,
        )
        self.assertIn("passed-quality-clean-tp4-oracle-sentinel", self.runner)
        self.assertIn("passed-quality-clean-tp4-oracle-with-comparison-caveat", self.runner)
        self.assertIn("cross_topology_target_or_baseline_mismatch_is_caveat_not_rejection", json.dumps(self.manifest))
        self.assertEqual(self.runner.count("dockerc run -d"), 1)

    def test_objective_quality_cache_zero_jq_fails_closed(self) -> None:
        match = re.search(
            r"quality_objective_gate\(\) \{\n  jq -e '(.*?)' \"\$1\"\n\}",
            self.runner,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        jq_filter = match.group(1)

        def usage(cached: int | None = 0) -> dict:
            details = {} if cached is None else {"cached_tokens": cached}
            return {"prompt_tokens_details": details}

        payload = {
            "pass_all": True,
            "exact_cases": [{"usage": usage()} for _ in range(7)],
            "repeat_case": {"runs": [{"usage": usage()} for _ in range(8)]},
            "long_context_case": {"usage": usage()},
        }

        def jq_passes(value: dict) -> bool:
            completed = subprocess.run(
                ["jq", "-e", jq_filter],
                input=json.dumps(value),
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            return completed.returncode == 0

        self.assertTrue(jq_passes(payload))
        missing = json.loads(json.dumps(payload))
        missing["repeat_case"]["runs"][3]["usage"] = usage(None)
        self.assertFalse(jq_passes(missing))
        nonzero = json.loads(json.dumps(payload))
        nonzero["long_context_case"]["usage"] = usage(1)
        self.assertFalse(jq_passes(nonzero))
        quality_failed = json.loads(json.dumps(payload))
        quality_failed["pass_all"] = False
        self.assertFalse(jq_passes(quality_failed))

    def test_both_oracle_pass_states_require_objective_quality(self) -> None:
        strong = (
            "depth_rc == 0 && objective_quality_ok == 1 && topology_ok == 1 "
            "&& target_ok == 1 && baseline_ok == 1"
        )
        caveated = "depth_rc == 0 && objective_quality_ok == 1 && topology_ok == 1"
        self.assertIn(strong, self.runner)
        self.assertIn(caveated, self.runner)

    def test_ext4_fresh_rank_cache_contract_is_fail_closed(self) -> None:
        cache = self.manifest["cache_contract"]
        self.assertEqual(cache["filesystem"], "ext4")
        self.assertTrue(cache["fresh"])
        self.assertTrue(cache["writable_ntfs_forbidden"])
        self.assertIn("output root must be ext4", self.runner)
        self.assertIn("cache root must be ext4", self.runner)
        self.assertIn("rank_${rank}_0", self.runner)
        self.assertIn("shared-compile-artifacts.txt", self.runner)
        self.assertIn("rank-cache-isolation-gate-failed", self.runner)

    def test_runtime_and_inputs_are_immutable(self) -> None:
        for token in (
            "f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f",
            "ac7509e2b1db40fec2f03dde1ed4e9dfdc2338c9",
            "0.27.2rc1.dev77+gac7509e2b.xpu",
            "0.1.12.3",
            "cb2bfd95e7ad9956dae5bc22ccfa575c8742847c963143291a21505533598202",
        ):
            self.assertIn(token, self.runner)

    def test_cleanup_nonreplacement_and_failure_preservation(self) -> None:
        interpretation = self.manifest["interpretation"]
        self.assertIsNone(interpretation["speed_floor"])
        self.assertFalse(interpretation["historical_replacement_allowed"])
        self.assertFalse(interpretation["descendant_expansion_is_automatic"])
        for token in (
            "repository must be clean",
            "trap cleanup_on_exit EXIT",
            "strict_postcleanup",
            "tp4-infrastructure-or-startup-failed",
            "passed-quality-clean-tp4-oracle-with-comparison-caveat",
            "quarantined-exact-depth-failed",
        ):
            self.assertIn(token, self.runner)

    def test_default_is_inert_and_launch_requires_exact_ack(self) -> None:
        self.assertTrue(self.manifest["execution"]["default_is_inert"])
        self.assertTrue(self.manifest["execution"]["one_server_lifetime"])
        self.assertIn("--check", self.runner)
        self.assertIn("--execute", self.runner)
        self.assertIn("exact acknowledgement required", self.runner)


if __name__ == "__main__":
    unittest.main()
