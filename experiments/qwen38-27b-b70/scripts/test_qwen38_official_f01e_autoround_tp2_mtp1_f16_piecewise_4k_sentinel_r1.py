#!/usr/bin/env python3
"""Inert contracts for the f01e TP2 PIECEWISE native-MTP1 4K sentinel."""

from __future__ import annotations

import json
import pathlib
import unittest


REPO = pathlib.Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp1-f16-piecewise-4k-sentinel-r1-prereg.json"
NOTE = LANE / "notes/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp1-f16-piecewise-4k-sentinel-r1-preregistration.md"
RUNNER = LANE / "scripts/run-20260826-qwen38-official-f01e-autoround-tp2-mtp1-f16-piecewise-4k-sentinel-r1.sh"


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.note = NOTE.read_text(encoding="utf-8")
        cls.runner = RUNNER.read_text(encoding="utf-8")

    def test_tuple_is_only_tp2_mtp1_piecewise_f16_exact_4k(self) -> None:
        run = self.manifest["run_identity"]
        self.assertEqual(run["tensor_parallel"], 2)
        self.assertEqual(run["mtp_depth"], 1)
        self.assertEqual(run["kv_cache_dtype"], "float16")
        self.assertEqual(run["graph_mode"], "PIECEWISE")
        self.assertEqual(run["graph_capture_sizes"], [1])
        self.assertEqual(self.manifest["exact_depth_contract"]["depths"], [4096])
        self.assertEqual(self.runner.count("--depth 4096"), 1)
        self.assertNotIn("--depth 8192", self.runner)
        self.assertNotIn("for depth in", self.runner)

    def test_clean_graph_target_and_eager_mechanism_evidence_are_pinned(self) -> None:
        target = self.manifest["parent_authority"]
        eager = self.manifest["same_topology_mtp1_eager_evidence"]
        self.assertEqual(
            target["piecewise_mtp0_4k"]["sha256"],
            "947a2459afdd8fb88e2ed6373a67e80cb2b4f20daaf78532d6ed362ee9472e94",
        )
        self.assertEqual(
            eager["exact_4k"]["sha256"],
            "83873b71a9d299729ed8ee985bae396fad616ecb16cbe74dcfe243bb515dbb16",
        )
        self.assertEqual(
            eager["verification_4k"]["sha256"],
            "2e38ee7119f927c67817fa15ed36afcd918012160479c1676cf9890531d6039c",
        )
        self.assertEqual(eager["verification_4k"]["drafted_tokens"], 71)
        self.assertEqual(eager["verification_4k"]["accepted_tokens"], 56)
        self.assertEqual(
            target["piecewise_mtp0_4k"]["output_token_ids_sha256"],
            eager["exact_4k"]["output_token_ids_sha256"],
        )
        self.assertIn("parent_ids_equal", self.runner)
        self.assertIn("candidate_ids == eager_ids == graph_ids", self.runner)

    def test_graph_and_both_worker_identity_are_fail_closed(self) -> None:
        for token in (
            "VLLM_XPU_ENABLE_XPU_GRAPH=1",
            'cudagraph_mode\":\"PIECEWISE',
            "enforce_eager=False",
            "Capturing CUDA graphs (mixed prefill-decode, PIECEWISE)",
            "Graph capturing finished",
            "world_size=2, local_world_size=2",
            "--tensor-parallel-size 2",
            "ZE_AFFINITY_MASK=0,1",
            "for rank in 0 1",
            'world_size=2 rank=$rank local_rank=$rank',
        ):
            self.assertIn(token, self.runner)
        self.assertIn("Capturing CUDA graphs (decode, FULL)", self.runner)
        self.assertNotIn("--enforce-eager", self.runner)
        self.assertNotIn("ONEAPI_DEVICE_SELECTOR", self.runner)

    def test_native_mtp_binding_and_isolated_acceptance(self) -> None:
        binding = self.manifest["speculator_binding"]
        self.assertIn("no external draft model", binding["type"])
        self.assertEqual(binding["method_requested"], "qwen3_next_mtp")
        self.assertEqual(binding["method_resolved_expected"], "mtp")
        self.assertEqual(binding["num_speculative_tokens"], 1)
        self.assertEqual(binding["mtp_tensor_count"], 29)
        for token in (
            '--speculative-config \'{"method":"qwen3_next_mtp","num_speculative_tokens":1}\'',
            "SpeculativeConfig(method='mtp'",
            "num_spec_tokens=1",
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
            "candidate_ids == eager_ids == graph_ids",
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
        for rank in range(2):
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

    def test_exact_one_cell_coverage_selector_and_no_other_depth(self) -> None:
        coverage = self.manifest["coverage_contract"]
        self.assertEqual(coverage["id"], "qwen38-tp2-vllm-xpu-autoround-f01e-mtp1-piecewise-depth")
        self.assertEqual(coverage["preregistration_state"], "missing-contract-and-selector")
        self.assertEqual(coverage["selectors"]["active_context_tokens"], 4096)
        self.assertEqual(coverage["selectors"]["graph_mode"], "PIECEWISE")
        self.assertEqual(coverage["selectors"]["kv"], "f16")
        self.assertEqual(coverage["other_cells_authorized"], 0)
        self.assertIn("Every non-4K exact cell is deliberately absent", self.note)
        self.assertNotIn("--depth 8192", self.runner)
        self.assertIn("semantic quality evidence only", self.note)

    def test_no_tp1_authority_auto_expansion_publication_or_replacement(self) -> None:
        interpretation = self.manifest["interpretation"]
        self.assertIsNone(interpretation["speed_floor"])
        self.assertTrue(interpretation["only_exact_4k_authorized"])
        self.assertFalse(interpretation["other_depths_tp_mtp_graph_or_kv_inferred"])
        self.assertFalse(interpretation["historical_replacement_allowed"])
        self.assertFalse(interpretation["automatic_publication"])
        self.assertFalse(interpretation["automatic_descendant_expansion"])
        self.assertFalse(interpretation["automatic_descendant_execution"])
        self.assertEqual(interpretation["other_site_or_matrix_cells_authorized"], 0)
        self.assertEqual(
            interpretation["protected_values_unchanged"],
            [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144],
        )
        self.assertIn("No other topology, graph mode, MTP depth, KV mode, context depth, or family cell is inherited", self.note)

    def test_fresh_static_modes_are_inert(self) -> None:
        execution = self.manifest["execution"]
        self.assertEqual(execution["port"], 19525)
        self.assertTrue(execution["fresh_roots_only"])
        self.assertTrue(execution["global_signal_and_exit_cleanup"])
        for token in ("--check", "--plan", "--execute", '"launch_performed":false'):
            self.assertIn(token, self.runner)
        self.assertEqual(self.runner.count("dockerc run -d"), 1)


if __name__ == "__main__":
    unittest.main()
