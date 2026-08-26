#!/usr/bin/env python3
"""Inert contracts for the f01e TP4 PIECEWISE native-MTP2 4K sentinel."""

from __future__ import annotations

import json
import pathlib
import unittest


REPO = pathlib.Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-26-qwen38-official-f01e-autoround-tp4-mtp2-f16-piecewise-4k-sentinel-r1-prereg.json"
NOTE = LANE / "notes/2026-08-26-qwen38-official-f01e-autoround-tp4-mtp2-f16-piecewise-4k-sentinel-r1-preregistration.md"
RUNNER = LANE / "scripts/run-20260826-qwen38-official-f01e-autoround-tp4-mtp2-f16-piecewise-4k-sentinel-r1.sh"


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.note = NOTE.read_text(encoding="utf-8")
        cls.runner = RUNNER.read_text(encoding="utf-8")

    def test_tuple_is_only_tp4_mtp2_piecewise_f16_exact_4k(self) -> None:
        run = self.manifest["run_identity"]
        self.assertEqual(run["tensor_parallel"], 4)
        self.assertEqual(run["mtp_depth"], 2)
        self.assertEqual(run["kv_cache_dtype"], "float16")
        self.assertEqual(run["graph_mode"], "PIECEWISE")
        self.assertEqual(run["graph_capture_sizes"], [1])
        self.assertEqual(self.manifest["exact_depth_contract"]["depths"], [4096])
        self.assertEqual(self.runner.count("--depth 4096"), 1)
        self.assertNotIn("--depth 8192", self.runner)
        self.assertNotIn("for depth in", self.runner)

    def test_clean_graph_target_and_eager_mechanism_evidence_are_pinned(self) -> None:
        target = self.manifest["parent_authority"]
        eager = self.manifest["same_topology_mtp2_eager_evidence"]
        self.assertEqual(
            target["eager_mtp0_4k"]["sha256"],
            "1dbba43c7ed816156f53b489e2287247e8a96f26a7d5f15a1a381d28f7e89e02",
        )
        self.assertEqual(
            target["piecewise_mtp0_4k"]["sha256"],
            "1e79d05c8e3ffe763a1f44a0d6def6b2b2f5b997aeec997e3841d7a447125deb",
        )
        self.assertEqual(
            eager["exact_4k"]["sha256"],
            "fdc3276d40f9bc6d265149e12308fe6a2a8d757a7a8e10ed5323da1eda08b8ac",
        )
        self.assertEqual(
            eager["verification_4k"]["sha256"],
            "9e87feab9799fd01e78e9c964ec71efefff66ec5f5c72c33c5b484cd05c30b56",
        )
        self.assertEqual(eager["verification_4k"]["drafted_tokens"], 94)
        self.assertEqual(eager["verification_4k"]["accepted_tokens"], 80)
        self.assertEqual(
            target["piecewise_mtp0_4k"]["output_token_ids_sha256"],
            eager["exact_4k"]["output_token_ids_sha256"],
        )
        self.assertIn("parent_ids_equal", self.runner)
        self.assertIn("candidate_ids == mtp2_eager_ids == piecewise_mtp0_ids == eager_mtp0_ids", self.runner)

    def test_graph_and_all_four_worker_identity_are_fail_closed(self) -> None:
        for token in (
            "VLLM_XPU_ENABLE_XPU_GRAPH=1",
            'cudagraph_mode\":\"PIECEWISE',
            "enforce_eager=False",
            "Capturing CUDA graphs (mixed prefill-decode, PIECEWISE)",
            "Graph capturing finished",
            "world_size=4, local_world_size=4",
            "--tensor-parallel-size 4",
            "ZE_AFFINITY_MASK=0,1,2,3",
            "for rank in 0 1 2 3",
            'world_size=4 rank=$rank local_rank=$rank',
        ):
            self.assertIn(token, self.runner)
        self.assertIn("Capturing CUDA graphs (decode, FULL)", self.runner)
        self.assertNotIn("--enforce-eager", self.runner)
        self.assertNotIn("ONEAPI_DEVICE_SELECTOR", self.runner)

    def test_native_mtp_binding_and_isolated_acceptance(self) -> None:
        binding = self.manifest["speculator_binding"]
        startup = self.manifest["run_identity"]["startup_speculator_identity"]
        self.assertIn("no external draft model", binding["type"])
        self.assertEqual(binding["method_requested"], "qwen3_next_mtp")
        self.assertEqual(binding["method_resolved_expected"], "mtp")
        self.assertEqual(binding["num_speculative_tokens"], 2)
        self.assertEqual(startup, {"method": "mtp", "num_spec_tokens": 2})
        self.assertEqual(binding["mtp_tensor_count"], 29)
        for token in (
            '--speculative-config \'{"method":"qwen3_next_mtp","num_speculative_tokens":2}\'',
            "SpeculativeConfig(method='mtp'",
            "num_spec_tokens=2",
            "drafted > 0",
            "0 < accepted <= drafted",
        ):
            self.assertIn(token, self.runner)
        body = self.runner.split("run_sentinel()", 1)[1].split("action=help", 1)[0]
        self.assertLess(body.index("metrics.before.prom"), body.index('"$depth_helper" --execute'))
        self.assertLess(body.index('"$depth_helper" --execute'), body.index("metrics.after-depth.prom"))
        self.assertLess(body.index("metrics.after-depth.prom"), body.index('"$quality_helper" --base-url'))

    def test_exact_target_parity_and_full_quality_are_required(self) -> None:
        for token in (
            "candidate_ids == mtp2_eager_ids == piecewise_mtp0_ids == eager_mtp0_ids",
            "candidate_exact and parent_ids_equal",
            "quality_contract_passed",
            "len(exact) == 7",
            'repeat.get("repeats") == 8',
            'len(repeat.get("unique_hashes", [])) == 1',
            'long_context.get("pass") is True',
            "len(comparisons) == 24",
            "all(cache_values) and len(cache_values) == 16",
            "--require-baseline",
            "quality_ok == 1",
        ):
            self.assertIn(token, self.runner)

    def test_rank_cache_model_and_cleanup_gates_are_required(self) -> None:
        for rank in range(4):
            self.assertIn(f'rank_{rank}_0', self.runner)
        for token in (
            "model-verification.json",
            '"$model_verifier" "$model_manifest" "$model"',
            "rank-cache-isolation-gate-failed",
            "trap cleanup_on_exit EXIT",
            "trap 'exit 130' INT",
            "trap 'exit 143' TERM",
            "strict_postcleanup",
            "repository must be clean",
            "canonical GPU campaign lock",
            "output root already exists",
            "cache root already exists",
        ):
            self.assertIn(token, self.runner)

    def test_quarantined_8k_is_excluded_from_exact_execution(self) -> None:
        excluded = self.manifest["excluded_evidence"]["current_f01e_tp4_mtp0_piecewise_8k"]
        self.assertEqual(excluded["state"], "quarantined-speedless")
        self.assertEqual(
            excluded["first_divergence"],
            {"one_based": 99, "candidate": 411, "target": 579},
        )
        self.assertEqual(
            excluded["candidate_ids_sha256"],
            "dd31856f45269d222efe0f6f5f1ac9342b6c9ae55e5ce9129fc02b27abdb7e8e",
        )
        self.assertIn("Every non-4K exact cell is deliberately absent", self.note)
        self.assertNotIn("--depth 8192", self.runner)
        self.assertIn("semantic quality evidence only", self.note)

    def test_eager_2k_risk_and_experimental_graph_scope_are_explicit(self) -> None:
        eager_2k = self.manifest["excluded_evidence"]["current_f01e_tp4_mtp2_eager_2k"]
        self.assertEqual(eager_2k["first_divergence"], {"one_based": 90, "candidate": 16539, "target": 59178})
        self.assertIn("experimental multi-GPU XPU Graph", self.note)
        self.assertIn("token 90", self.note)

    def test_exact_one_cell_coverage_selector_and_no_other_depth(self) -> None:
        coverage = self.manifest["coverage_contract"]
        self.assertEqual(coverage["proposal_id"], "qwen38-tp4-vllm-xpu-autoround-f01e-mtp2-piecewise-depth")
        self.assertEqual(coverage["state"], "proposed-not-written-to-family")
        self.assertEqual(coverage["axis"]["values"], [0, 2048, 4096, 8192, 16384, 24576, 32768])
        self.assertEqual(coverage["proposed_rules"][0]["count"], 6)
        self.assertEqual(coverage["proposed_rules"][1]["values"], [4096])
        self.assertEqual(coverage["maximum_cells_this_packet_can_fill"], 1)
        self.assertEqual(coverage["other_cells_authorized"], 0)

    def test_mtp1_graph_precedent_is_topology_only(self) -> None:
        precedent = self.manifest["graph_topology_precedent"]
        self.assertEqual(precedent["result"]["sha256"], "06d42cc4a1a65e870ee942ca29f292f7a5ba98d10d90657bdd96a5ba10c2ab02")
        self.assertIn("topology", precedent["authority"])
        self.assertIn("do not transfer", precedent["authority"])

    def test_no_tp1_authority_auto_expansion_publication_or_replacement(self) -> None:
        interpretation = self.manifest["interpretation"]
        self.assertIsNone(interpretation["speed_floor"])
        self.assertTrue(interpretation["no_inherited_tp1_authority"])
        self.assertFalse(interpretation["historical_replacement_allowed"])
        self.assertFalse(interpretation["automatic_publication"])
        self.assertFalse(interpretation["automatic_descendant_expansion"])
        self.assertFalse(interpretation["automatic_descendant_execution"])
        self.assertEqual(interpretation["other_site_or_matrix_cells_authorized"], 0)
        self.assertEqual(
            interpretation["protected_values_unchanged"],
            [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144],
        )
        self.assertIn("No TP1 oracle or authority is inherited", self.note)

    def test_fresh_static_modes_are_inert(self) -> None:
        execution = self.manifest["execution"]
        self.assertEqual(execution["port"], 19528)
        self.assertEqual(execution["startup_timeout_seconds"], 1200)
        self.assertTrue(execution["fresh_roots_only"])
        self.assertTrue(execution["global_signal_and_exit_cleanup"])
        for token in ("--check", "--plan", "--execute", '"launch_performed":false'):
            self.assertIn(token, self.runner)
        self.assertEqual(self.runner.count("dockerc run -d"), 1)


if __name__ == "__main__":
    unittest.main()
