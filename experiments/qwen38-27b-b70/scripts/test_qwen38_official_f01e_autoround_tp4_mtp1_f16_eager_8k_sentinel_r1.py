#!/usr/bin/env python3
"""Inert tests for the current-f01e AutoRound TP4/MTP1 sentinel."""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import unittest


REPO = pathlib.Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-26-qwen38-official-f01e-autoround-tp4-mtp1-f16-eager-8k-sentinel-r1-prereg.json"
RUNNER = LANE / "scripts/run-20260826-qwen38-official-f01e-autoround-tp4-mtp1-f16-eager-8k-sentinel-r1.sh"


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.runner = RUNNER.read_text(encoding="utf-8")

    def test_exact_tp4_mtp1_f16_eager_identity(self) -> None:
        run = self.manifest["run_identity"]
        self.assertEqual(run["tensor_parallel"], 4)
        self.assertEqual(run["mtp_depth"], 1)
        self.assertEqual(run["kv_cache_dtype"], "float16")
        self.assertEqual(run["graph_mode"], "off")
        self.assertEqual(run["gpu_affinity"], "0,1,2,3")
        self.assertEqual(run["gpu_memory_utilization"], 0.6)
        self.assertEqual(run["max_num_seqs"], 1)
        self.assertEqual(run["max_model_len"], 32896)
        self.assertEqual(self.manifest["exact_depth_contract"]["depths"], [8192])

    def test_native_mtp1_argument_and_startup_identity_are_exact(self) -> None:
        for token in (
            '--speculative-config \'{"method":"qwen3_next_mtp","num_speculative_tokens":1}\'',
            "speculative_config=SpeculativeConfig(method='mtp'",
            "num_spec_tokens=1",
            "quantization=inc",
            "enforce_eager=True",
            "kv_cache_dtype=auto",
            "served_model=qwen38-official-f01e-autoround-tp4-mtp1",
        ):
            self.assertIn(token, self.runner)
        self.assertNotIn("--kv-cache-dtype", self.runner)
        self.assertNotIn("ONEAPI_DEVICE_SELECTOR", self.runner)

    def test_embedded_speculator_is_pinned(self) -> None:
        binding = self.manifest["speculator_binding"]
        self.assertEqual(binding["method_requested"], "qwen3_next_mtp")
        self.assertEqual(binding["method_resolved_expected"], "mtp")
        self.assertEqual(binding["num_speculative_tokens"], 1)
        self.assertEqual(binding["mtp_tensor_count"], 29)
        self.assertEqual(
            binding["mtp_tensor_sha256"],
            "94102b67c6b84e65dbb9bae37c00bd88ac1a43ff577ce65fd8842d231c7e89de",
        )
        self.assertIn("embedded MTP tensor binding contract failed", self.runner)

    def test_same_topology_parent_receipts_are_frozen(self) -> None:
        parent = self.manifest["parent_oracle"]
        self.assertEqual(
            parent["terminal_receipt"]["sha256"],
            "779c64418c9cec0654f5107bfc83ccb5263f88d12b9481dd87a5ec301d170a16",
        )
        self.assertEqual(
            parent["exact_8k"]["sha256"],
            "49ea5caae577dae86bb52378e84a6ad45da051ae403904158751903393121d9e",
        )
        self.assertEqual(
            parent["exact_8k"]["output_token_ids_sha256"],
            "34e792ccf3c1d795b686750f27990de2ca605c22046c97b3fff8ad0a7fc82e53",
        )
        self.assertIn("same-topology TP4/MTP0", self.runner)

    def test_quality_baseline_is_the_tp4_parent(self) -> None:
        quality = self.manifest["quality_contract"]
        self.assertIn("tp4-mtp0-f16-eager-8k-oracle", quality["baseline"])
        self.assertEqual(
            quality["baseline_sha256"],
            "2019240440a9ec03bf7904317b4d14a8499631b91183fd06430eedb3eb19d5ca",
        )
        self.assertIn("2019240440a9ec03bf7904317b4d14a8499631b91183fd06430eedb3eb19d5ca", self.runner)

    def test_acceptance_snapshots_bracket_only_exact_request(self) -> None:
        body = self.runner.split("run_sentinel()", 1)[1].split("action=help", 1)[0]
        before = body.index('metrics.before.prom')
        depth = body.index('"$depth_helper" --execute')
        after = body.index('metrics.after-depth.prom')
        quality = body.index('"$quality_helper" --base-url')
        self.assertLess(before, depth)
        self.assertLess(depth, after)
        self.assertLess(after, quality)
        gate = self.manifest["acceptance_contract"]["gate"]
        self.assertIn("drafted delta > 0", gate)
        self.assertIn("accepted delta > 0", gate)
        self.assertIn("accepted <= drafted", gate)
        self.assertIn("drafted > 0 and 0 < accepted <= drafted", self.runner)

    def test_same_topology_target_parity_is_exact(self) -> None:
        self.assertIn("candidate_ids == target_ids", self.runner)
        self.assertIn("same_topology_target_verification", self.runner)
        self.assertIn("same-image same-topology TP4/MTP0", self.runner)
        self.assertIn("target_ok == 1", self.runner)

    def test_objective_cache_zero_gate_fails_closed(self) -> None:
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

        def passes(value: dict) -> bool:
            return subprocess.run(
                ["jq", "-e", jq_filter], input=json.dumps(value), text=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
            ).returncode == 0

        self.assertTrue(passes(payload))
        missing = json.loads(json.dumps(payload))
        missing["exact_cases"][2]["usage"] = usage(None)
        self.assertFalse(passes(missing))
        nonzero = json.loads(json.dumps(payload))
        nonzero["long_context_case"]["usage"] = usage(1)
        self.assertFalse(passes(nonzero))

    def test_both_pass_states_require_acceptance_target_and_objective_quality(self) -> None:
        mandatory = (
            "depth_rc == 0 && objective_quality_ok == 1 && topology_ok == 1 "
            "&& acceptance_ok == 1 && target_ok == 1"
        )
        self.assertEqual(self.runner.count(mandatory), 2)
        self.assertIn("baseline_ok == 1", self.runner)
        self.assertIn("passed-quality-clean-tp4-mtp1-with-baseline-caveat", self.runner)

    def test_four_workers_and_graph_off_are_fail_closed(self) -> None:
        for token in (
            "--tensor-parallel-size 4",
            "ZE_AFFINITY_MASK=0,1,2,3",
            "VLLM_XPU_ENABLE_XPU_GRAPH=0",
            "VLLM_XPU_GRAPH=0",
            "world_size=4, local_world_size=4",
            "for rank in 0 1 2 3",
            "tp4-worker-topology-gate-failed",
        ):
            self.assertIn(token, self.runner)

    def test_ext4_rank_cache_isolation_is_preserved(self) -> None:
        cache = self.manifest["cache_contract"]
        self.assertEqual(cache["filesystem"], "ext4")
        self.assertTrue(cache["writable_ntfs_forbidden"])
        self.assertIn("rank_${rank}_0", self.runner)
        self.assertIn("shared-compile-artifacts.txt", self.runner)
        self.assertIn("rank-cache-isolation-gate-failed", self.runner)

    def test_quarantines_cleanup_and_nonreplacement_are_explicit(self) -> None:
        for token in (
            "quarantined-acceptance-failed",
            "quarantined-target-verification-failed",
            "quarantined-objective-quality-failed",
            "quarantined-exact-depth-failed",
            "trap cleanup_on_exit EXIT",
            "strict_postcleanup",
            "repository must be clean",
        ):
            self.assertIn(token, self.runner)
        interpretation = self.manifest["interpretation"]
        self.assertIsNone(interpretation["speed_floor"])
        self.assertFalse(interpretation["historical_replacement_allowed"])
        self.assertFalse(interpretation["descendant_expansion_is_automatic"])

    def test_default_is_inert_and_one_server_lifetime(self) -> None:
        self.assertTrue(self.manifest["execution"]["default_is_inert"])
        self.assertTrue(self.manifest["execution"]["one_server_lifetime"])
        self.assertEqual(self.runner.count("dockerc run -d"), 1)
        self.assertIn("exact acknowledgement required", self.runner)


if __name__ == "__main__":
    unittest.main()
