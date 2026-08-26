#!/usr/bin/env python3
"""Inert tests for the current-f01e AutoRound TP2/MTP4 exact-4K sentinel."""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import unittest


REPO = pathlib.Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-4k-sentinel-r1-prereg.json"
RUNNER = LANE / "scripts/run-20260826-qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-4k-sentinel-r1.sh"


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.runner = RUNNER.read_text(encoding="utf-8")

    def test_exact_tp2_mtp4_identity(self) -> None:
        run = self.manifest["run_identity"]
        self.assertEqual(run["tensor_parallel"], 2)
        self.assertEqual(run["mtp_depth"], 4)
        self.assertEqual(run["speculative_config"], {"method": "qwen3_next_mtp", "num_speculative_tokens": 4})
        self.assertEqual(run["startup_speculator_identity"], {"method": "mtp", "num_spec_tokens": 4})
        self.assertEqual(run["kv_cache_dtype"], "float16")
        self.assertEqual(run["graph_mode"], "off")
        self.assertEqual(run["gpu_affinity"], "0,1")
        self.assertEqual(run["gpu_memory_utilization"], 0.6)
        self.assertEqual(self.manifest["exact_depth_contract"]["depths"], [4096])

    def test_native_mtp4_binding_is_exact(self) -> None:
        self.assertIn("model_extra_tensors.safetensors", self.runner)
        self.assertIn("94102b67c6b84e65dbb9bae37c00bd88ac1a43ff577ce65fd8842d231c7e89de", self.runner)
        self.assertIn("mtp_num_hidden_layers == 1", self.runner)
        self.assertIn("($m|length) == 29", self.runner)
        self.assertIn("--speculative-config", self.runner)
        self.assertIn('"method":"qwen3_next_mtp","num_speculative_tokens": 4', self.runner)
        self.assertIn("method='mtp'", self.runner)
        self.assertIn("num_spec_tokens=4", self.runner)
        self.assertNotIn("speculative_config_absent", json.dumps(self.manifest))

    def test_scoped_mtp3_parent_is_frozen(self) -> None:
        parent = self.manifest["parent_oracle"]
        self.assertIn("tp2-mtp3", parent["root"])
        self.assertEqual(parent["terminal_receipt_sha256"], "977a0aba4fed5510fb8ec568e3a9eb99df4f86a872478878e8c85d147899b64c")
        self.assertEqual(parent["arm_result_sha256"], "ed3f1b46ac8a6a6ed4ec5592a9a7621e82e1d5a8b59a30c73adc04af41b8ec2f")
        self.assertEqual(parent["quality_receipt_sha256"], "f74046dd65642d9fa8cb177fed12bba27bbdeada1a7ff8fb5273bf3966245e2b")
        self.assertEqual(parent["exact_4k_receipt_sha256"], "daf7201c641185f1dd4e54ff1661c7a817d49979afe0d06c3661ef5e2bad1ec7")
        self.assertEqual(parent["verification_4k_receipt_sha256"], "b1f0b4701936c4b7ca7cb5ca9e85ab91e394336ebca8b0cd1fed79a9dbc6a756")
        self.assertEqual(parent["output_token_ids_sha256"], "3febb16ef2033c31e17817c6753ccdb95ad6e39db394ed4476ee12fb86af78b0")
        self.assertEqual((parent["drafted_tokens"], parent["accepted_tokens"]), (123, 86))
        for digest in (parent["terminal_receipt_sha256"], parent["arm_result_sha256"],
                       parent["quality_receipt_sha256"], parent["exact_4k_receipt_sha256"],
                       parent["verification_4k_receipt_sha256"]):
            self.assertIn(digest, self.runner)
        for gate in ("frozen TP2/MTP3 scoped parent terminal failed",
                     "frozen TP2/MTP3 scoped parent arm failed",
                     "frozen TP2/MTP3 scoped parent quality failed",
                     "frozen TP2/MTP3 scoped parent 4K depth failed",
                     "frozen TP2/MTP3 scoped parent 4K verification failed"):
            self.assertIn(gate, self.runner)

    def test_same_topology_mtp0_target_is_frozen(self) -> None:
        target = self.manifest["target_oracle"]
        self.assertIn("tp2-mtp0", target["root"])
        self.assertEqual(target["exact_4k_receipt_sha256"], "6e32b0a05f7e355bf21c5e3ebd0e04a16fbf3d54bc39890aa8740b3a5430f187")
        self.assertEqual(target["terminal_receipt_sha256"], "63fe2e8a85db47af331743b93b1c6e181f930775104f19483eb7b9e1da0f2c60")
        self.assertEqual(target["quality_receipt_sha256"], "ef15f39a848d262a4582b1ab6c9a2f10713ecfbcae02497bc4462c8ae5a3af96")
        self.assertEqual(target["output_token_ids_sha256"], "3febb16ef2033c31e17817c6753ccdb95ad6e39db394ed4476ee12fb86af78b0")
        for digest in (target["exact_4k_receipt_sha256"], target["terminal_receipt_sha256"],
                       target["quality_receipt_sha256"]):
            self.assertIn(digest, self.runner)

    def test_fresh_identity_and_parent_topology_are_preserved(self) -> None:
        execution = self.manifest["execution"]
        self.assertEqual(execution["port"], 19518)
        self.assertIn("tp2-mtp4", execution["output_root"])
        self.assertIn("tp2-mtp4", execution["cache_root"])
        self.assertNotIn("tp2-mtp0", execution["output_root"])
        for token in (
            "port=19518", "--tensor-parallel-size 2", "--gpu-memory-utilization 0.60",
            "--enforce-eager", "ZE_AFFINITY_MASK=0,1",
            "VLLM_XPU_ENABLE_XPU_GRAPH=0", "VLLM_XPU_GRAPH=0",
            "world_size=2, local_world_size=2", "for rank in 0 1",
        ):
            self.assertIn(token, self.runner)
        self.assertNotIn("ONEAPI_DEVICE_SELECTOR", self.runner)

    def test_acceptance_gate_is_isolated_positive_and_conserved(self) -> None:
        contract = self.manifest["acceptance_contract"]
        self.assertIn("immediately before and after only", contract["snapshot_scope"])
        self.assertIn("accepted_delta <= drafted_delta", contract["gate"])
        self.assertIn('curl -fsS "http://127.0.0.1:$port/metrics" > "$root/metrics.before.prom"', self.runner)
        self.assertIn('curl -fsS "http://127.0.0.1:$port/metrics" > "$root/metrics.after.prom"', self.runner)
        self.assertLess(self.runner.rindex("metrics.before.prom"), self.runner.rindex('"$depth_helper" --execute'))
        self.assertLess(self.runner.rindex('"$depth_helper" --execute'), self.runner.rindex("metrics.after.prom"))
        for token in ("drafted > 0", "0 < accepted <= drafted", "a_draft >= b_draft", "a_accept >= b_accept"):
            self.assertIn(token, self.runner)
        self.assertIn("acceptance.conserved == true", self.runner)

    def test_target_parity_is_strong_and_same_topology(self) -> None:
        self.assertIn("candidate_ids == target_ids", self.runner)
        self.assertIn('target_verification.passed == true', self.runner)
        self.assertIn('"exact_depth_and_cache_zero_passed": int(depth_rc) == 0', self.runner)
        self.assertIn("same-topology TP2/MTP0/eager/F16", self.runner)
        self.assertIn("quarantined-target-parity-failed", self.runner)
        self.assertNotIn("comparison-caveat", self.runner)

    def test_objective_quality_and_all_16_cache_records_are_required(self) -> None:
        self.assertIn("--require-baseline", self.runner)
        self.assertIn("--repeat-runs 8", self.runner)
        self.assertIn("--long-context-tokens 8192", self.runner)
        self.assertIn('($q.pass_all == true)', self.runner)
        self.assertIn("length == 16", self.runner)
        self.assertIn("cached_tokens? == 0", self.runner)
        self.assertIn("baseline_match_all == true", self.runner)
        strong = "quality_rc != 0 || objective_quality_ok == 0 || baseline_ok == 0"
        self.assertIn(strong, self.runner)

    def test_objective_quality_jq_fails_closed(self) -> None:
        match = re.search(r"quality_objective_gate\(\) \{\n  jq -e '(.*?)' \"\$1\"\n\}", self.runner, re.DOTALL)
        self.assertIsNotNone(match)
        jq_filter = match.group(1)

        def usage(cached: int | None = 0) -> dict:
            return {"prompt_tokens_details": {} if cached is None else {"cached_tokens": cached}}

        payload = {
            "pass_all": True,
            "exact_cases": [{"usage": usage()} for _ in range(7)],
            "repeat_case": {"runs": [{"usage": usage()} for _ in range(8)]},
            "long_context_case": {"usage": usage()},
        }

        def passes(value: dict) -> bool:
            return subprocess.run(["jq", "-e", jq_filter], input=json.dumps(value), text=True,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0

        self.assertTrue(passes(payload))
        payload["repeat_case"]["runs"][0]["usage"] = usage(None)
        self.assertFalse(passes(payload))

    def test_cache_and_cleanup_are_fail_closed(self) -> None:
        cache = self.manifest["cache_contract"]
        self.assertEqual(cache["filesystem"], "ext4")
        self.assertTrue(cache["fresh"])
        for token in ("output root must be ext4", "cache root must be ext4", "rank_${rank}_0",
                      "shared-compile-artifacts.txt", "rank-cache-isolation-gate-failed",
                      "strict_postcleanup", "trap cleanup_on_exit EXIT"):
            self.assertIn(token, self.runner)

    def test_tp1_and_tp4_risks_force_sentinel_scope(self) -> None:
        history = self.manifest["historical_risk"]
        self.assertIn("token 99", history["tp1_mtp4"])
        self.assertIn("32K", history["tp1_mtp4"])
        self.assertIn("token 99", history["tp4_mtp4"])
        self.assertIn("structurally quarantined", history["tp4_mtp4"])
        self.assertIn("single exact-4K sentinel", history["sentinel_only_reason"])
        self.assertIn("16K/24K/32K remain unauthorized", history["sentinel_only_reason"])
        self.assertIsNone(self.manifest["interpretation"]["speed_floor"])
        self.assertFalse(self.manifest["interpretation"]["historical_replacement_allowed"])

    def test_existing_tp2_mtp4_8k_failure_is_frozen_and_stays_quarantined(self) -> None:
        prior = self.manifest["historical_risk"]["tp2_mtp4_8k_quarantine"]
        self.assertEqual(prior["sha256"], "ae0828434248862bc9eaa8bcb82fe6a74d20b8007dc186b3f72477e68a38a3d3")
        self.assertEqual(prior["status"], "quarantined-target-parity-failed")
        self.assertEqual(prior["first_divergence_one_based"], 99)
        self.assertEqual((prior["candidate_token"], prior["target_token"]), (411, 579))
        self.assertEqual(prior["site_measured_speed_cells"], 0)
        for token in (
            "frozen TP2/MTP4 exact-8K quarantine changed",
            ".diagnostic_point.x == 8192",
            ".target_failure.first_divergence.one_based == 99",
            ".authority.site_measured_speed_cells == 0",
        ):
            self.assertIn(token, self.runner)

    def test_failure_is_lower_grade_and_non_authoritative(self) -> None:
        interpretation = self.manifest["interpretation"]
        self.assertTrue(interpretation["failure_retains_lower_grade_evidence"])
        self.assertFalse(interpretation["site_publication_automatic"])
        self.assertFalse(interpretation["descendant_expansion_is_automatic"])
        self.assertFalse(interpretation["depth_expansion_authorized"])
        self.assertFalse(interpretation["descendant_execution_authorized"])
        self.assertEqual(interpretation["protected_decode_values_unchanged"],
                         [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144])
        for state in ("quarantined-target-parity-failed", "quarantined-acceptance-failed",
                      "quarantined-quality-failed", "quarantined-exact-depth-failed"):
            self.assertIn(state, self.runner)
        self.assertIn('"publication_authorized": False', self.runner)
        self.assertIn('"depth_expansion_authorized": False', self.runner)
        self.assertIn('"descendant_expansion_authorized": False', self.runner)
        self.assertIn(".interpretation.depth_expansion_authorized == false", self.runner)

    def test_full_quality_battery_keeps_8k_needle(self) -> None:
        self.assertIn("--long-context-tokens 8192", self.runner)
        self.assertNotIn("--long-context-tokens 4096", self.runner)

    def test_default_is_inert_and_ack_is_exact(self) -> None:
        self.assertTrue(self.manifest["execution"]["default_is_inert"])
        self.assertEqual(self.runner.count("dockerc run -d"), 1)
        self.assertIn("--check", self.runner)
        self.assertIn("--execute", self.runner)
        self.assertIn("exact acknowledgement required", self.runner)


if __name__ == "__main__":
    unittest.main()
