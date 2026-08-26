#!/usr/bin/env python3
"""Inert contract tests for the f01e TP1 PIECEWISE native-MTP1 4K sentinel."""

from __future__ import annotations

import json
import pathlib
import unittest


REPO = pathlib.Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-26-qwen38-official-f01e-autoround-tp1-mtp1-f16-piecewise-4k-sentinel-r1-prereg.json"
NOTE = LANE / "notes/2026-08-26-qwen38-official-f01e-autoround-tp1-mtp1-f16-piecewise-4k-sentinel-r1-preregistration.md"
RUNNER = LANE / "scripts/run-20260826-qwen38-official-f01e-autoround-tp1-mtp1-f16-piecewise-4k-sentinel-r1.sh"


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.note = NOTE.read_text(encoding="utf-8")
        cls.runner = RUNNER.read_text(encoding="utf-8")

    def test_tuple_is_only_tp1_mtp1_piecewise_f16_exact_4k(self) -> None:
        run = self.manifest["run_identity"]
        self.assertEqual(run["tensor_parallel"], 1)
        self.assertEqual(run["mtp_depth"], 1)
        self.assertEqual(run["kv_cache_dtype"], "float16")
        self.assertEqual(run["graph_mode"], "PIECEWISE")
        self.assertEqual(run["graph_capture_sizes"], [1])
        self.assertEqual(self.manifest["exact_depth_contract"]["depths"], [4096])
        self.assertIn("--depth 4096", self.runner)
        self.assertNotIn("--depth 8192", self.runner)

    def test_clean_dual_parents_and_adjudication_are_pinned(self) -> None:
        parent = self.manifest["parent_authority"]
        self.assertEqual(
            parent["human_adjudication"]["sha256"],
            "565687bd30aea3b07c3bd4212f3fdcfb961809258403ba2bcdef82fd03e64a49",
        )
        self.assertEqual(
            parent["eager_mtp0_4k"]["sha256"],
            "c9dbfb8b9cf8ef23bea5ebe2cb3199c82d678988106e2f619221236e4726dd9e",
        )
        self.assertEqual(
            parent["piecewise_mtp0_4k"]["sha256"],
            "dbe7523591ee8bf5722eeba2555dfa9243d00b35bf80bb758b2a26b2fa50b027",
        )
        self.assertEqual(
            parent["eager_mtp0_4k"]["output_token_ids_sha256"],
            parent["piecewise_mtp0_4k"]["output_token_ids_sha256"],
        )
        self.assertIn("parent_ids_equal", self.runner)
        self.assertIn("candidate_ids == eager_ids == graph_ids", self.runner)

    def test_graph_identity_is_fail_closed(self) -> None:
        for token in (
            "VLLM_XPU_ENABLE_XPU_GRAPH=1",
            "cudagraph_mode\":\"PIECEWISE",
            "enforce_eager=False",
            "Capturing CUDA graphs (mixed prefill-decode, PIECEWISE)",
            "Graph capturing finished",
            "world_size=1 rank=0 local_rank=0",
            "TP rank 0",
        ):
            self.assertIn(token, self.runner)
        self.assertIn("Capturing CUDA graphs (decode, FULL)", self.runner)
        self.assertNotIn("--enforce-eager", self.runner)

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

    def test_full_quality_is_composed_and_not_return_code_only(self) -> None:
        for token in (
            "quality_contract_passed",
            "len(exact) == 7",
            'repeat.get("repeats") == 8',
            'len(repeat.get("unique_hashes", [])) == 1',
            'long_context.get("pass") is True',
            "len(comparisons) == 24",
            "all(cache_values) and len(cache_values) == 16",
            "--require-baseline",
        ):
            self.assertIn(token, self.runner)
        self.assertIn("quality_ok == 1", self.runner)

    def test_historical_corruption_and_8k_exclusion_are_explicit(self) -> None:
        caveat = self.manifest["historical_corruption_caveat"]
        self.assertIn("token 99", caveat["known_signature"])
        self.assertIn("411", caveat["known_signature"])
        self.assertIn("579", caveat["known_signature"])
        self.assertIn("dd31856f", caveat["known_signature"])
        self.assertIn("4K rather than 8K", self.note)
        self.assertIn("does not clear 8K", caveat["forbidden_inference"])

    def test_no_auto_expansion_publication_or_replacement(self) -> None:
        interpretation = self.manifest["interpretation"]
        self.assertIsNone(interpretation["speed_floor"])
        self.assertFalse(interpretation["historical_replacement_allowed"])
        self.assertFalse(interpretation["automatic_publication"])
        self.assertFalse(interpretation["automatic_descendant_expansion"])
        self.assertFalse(interpretation["automatic_descendant_execution"])
        self.assertEqual(
            interpretation["protected_values_unchanged"],
            [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144],
        )

    def test_fresh_isolated_execution_and_cleanup(self) -> None:
        execution = self.manifest["execution"]
        self.assertEqual(execution["port"], 19517)
        self.assertTrue(execution["fresh_roots_only"])
        self.assertTrue(execution["global_signal_and_exit_cleanup"])
        for token in (
            "repository must be clean",
            "canonical GPU campaign lock",
            "trap cleanup_on_exit EXIT",
            "trap 'exit 130' INT",
            "trap 'exit 143' TERM",
            "strict_postcleanup",
            "output root already exists",
            "cache root already exists",
            "output root must be ext4",
            "cache root must be ext4",
        ):
            self.assertIn(token, self.runner)

    def test_static_modes_are_inert(self) -> None:
        for token in ("--check", "--plan", "--execute", '"launch_performed":false'):
            self.assertIn(token, self.runner)
        self.assertEqual(self.runner.count("dockerc run -d"), 1)


if __name__ == "__main__":
    unittest.main()
