#!/usr/bin/env python3
"""Inert tests for the current-f01e AutoRound TP4/MTP4 sentinel."""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import unittest


REPO = pathlib.Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-26-qwen38-official-f01e-autoround-tp4-mtp4-f16-eager-8k-sentinel-r1-prereg.json"
RUNNER = LANE / "scripts/run-20260826-qwen38-official-f01e-autoround-tp4-mtp4-f16-eager-8k-sentinel-r1.sh"


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.runner = RUNNER.read_text(encoding="utf-8")

    def test_exact_tp4_mtp4_identity(self) -> None:
        run = self.manifest["run_identity"]
        self.assertEqual(run["tensor_parallel"], 4)
        self.assertEqual(run["mtp_depth"], 4)
        self.assertEqual(run["speculative_config"], {"method": "qwen3_next_mtp", "num_speculative_tokens": 4})
        self.assertEqual(run["startup_speculator_identity"], {"method": "mtp", "num_spec_tokens": 4})
        self.assertEqual(run["kv_cache_dtype"], "float16")
        self.assertEqual(run["graph_mode"], "off")
        self.assertEqual(run["gpu_affinity"], "0,1,2,3")
        self.assertEqual(run["gpu_memory_utilization"], 0.6)
        self.assertEqual(self.manifest["exact_depth_contract"]["depths"], [8192])

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

    def test_same_topology_parent_is_frozen(self) -> None:
        parent = self.manifest["parent_oracle"]
        self.assertIn("tp4-mtp0", parent["root"])
        self.assertEqual(parent["exact_8k_receipt_sha256"], "49ea5caae577dae86bb52378e84a6ad45da051ae403904158751903393121d9e")
        self.assertEqual(parent["terminal_receipt_sha256"], "779c64418c9cec0654f5107bfc83ccb5263f88d12b9481dd87a5ec301d170a16")
        self.assertEqual(parent["quality_receipt_sha256"], "2019240440a9ec03bf7904317b4d14a8499631b91183fd06430eedb3eb19d5ca")
        self.assertEqual(parent["output_token_ids_sha256"], "34e792ccf3c1d795b686750f27990de2ca605c22046c97b3fff8ad0a7fc82e53")
        for digest in (parent["exact_8k_receipt_sha256"], parent["terminal_receipt_sha256"], parent["quality_receipt_sha256"]):
            self.assertIn(digest, self.runner)
        self.assertIn("same-topology TP4", self.runner)
        self.assertNotIn("tp1-f16-graphmodes-depth", self.runner)
        self.assertNotIn("nightly-strict-20260823/tp1-mtp0", self.runner)

    def test_fresh_identity_and_parent_topology_are_preserved(self) -> None:
        execution = self.manifest["execution"]
        self.assertEqual(execution["port"], 19485)
        self.assertIn("tp4-mtp4", execution["output_root"])
        self.assertIn("tp4-mtp4", execution["cache_root"])
        self.assertNotIn("tp4-mtp0", execution["output_root"])
        for token in (
            "port=19485", "--tensor-parallel-size 4", "--gpu-memory-utilization 0.60",
            "--enforce-eager", "ZE_AFFINITY_MASK=0,1,2,3",
            "VLLM_XPU_ENABLE_XPU_GRAPH=0", "VLLM_XPU_GRAPH=0",
            "world_size=4, local_world_size=4", "for rank in 0 1 2 3",
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
        self.assertIn("same-topology TP4/MTP0/eager/F16", self.runner)
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

    def test_tp1_32k_fatal_is_profile_local_risk_only(self) -> None:
        history = self.manifest["historical_context"]
        risk = history["tp1_mtp4_32k_fatal"]
        self.assertIn("TP1/MTP4", risk)
        self.assertIn("exact 32K", risk)
        self.assertIn("profile-local risk", risk)
        self.assertIn("does not predict, close, or weaken", risk)
        self.assertIsNone(self.manifest["interpretation"]["speed_floor"])
        self.assertFalse(self.manifest["interpretation"]["historical_replacement_allowed"])

    def test_failure_is_lower_grade_and_non_authoritative(self) -> None:
        interpretation = self.manifest["interpretation"]
        self.assertTrue(interpretation["failure_retains_lower_grade_evidence"])
        self.assertFalse(interpretation["site_publication_automatic"])
        self.assertFalse(interpretation["descendant_expansion_is_automatic"])
        for state in ("quarantined-target-parity-failed", "quarantined-acceptance-failed",
                      "quarantined-quality-failed", "quarantined-exact-depth-failed"):
            self.assertIn(state, self.runner)
        self.assertIn('"publication_authorized": False', self.runner)
        self.assertIn('"descendant_expansion_authorized": False', self.runner)

    def test_default_is_inert_and_ack_is_exact(self) -> None:
        self.assertTrue(self.manifest["execution"]["default_is_inert"])
        self.assertEqual(self.runner.count("dockerc run -d"), 1)
        self.assertIn("--check", self.runner)
        self.assertIn("--execute", self.runner)
        self.assertIn("exact acknowledgement required", self.runner)


if __name__ == "__main__":
    unittest.main()
