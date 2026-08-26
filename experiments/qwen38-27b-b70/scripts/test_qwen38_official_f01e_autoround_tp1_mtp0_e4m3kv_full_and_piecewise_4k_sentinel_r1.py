#!/usr/bin/env python3
"""Inert contracts for the f01e TP1/MTP0 FULL_AND_PIECEWISE E4M3 4K sentinel."""

from __future__ import annotations

import importlib.util
import json
import pathlib
import unittest


REPO = pathlib.Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-26-qwen38-official-f01e-autoround-tp1-mtp0-e4m3kv-full-and-piecewise-4k-sentinel-r1-prereg.json"
NOTE = LANE / "notes/2026-08-26-qwen38-official-f01e-autoround-tp1-mtp0-e4m3kv-full-and-piecewise-4k-sentinel-r1-preregistration.md"
RUNNER = LANE / "scripts/run-20260826-qwen38-official-f01e-autoround-tp1-mtp0-e4m3kv-full-and-piecewise-4k-sentinel-r1.sh"
FAMILY = REPO / "families/qwen-27b.json"


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.note = NOTE.read_text(encoding="utf-8")
        cls.runner = RUNNER.read_text(encoding="utf-8")

    def test_exact_tuple_and_single_depth(self) -> None:
        run = self.manifest["run_identity"]
        self.assertEqual(run["tensor_parallel"], 1)
        self.assertEqual(run["mtp_depth"], 0)
        self.assertIsNone(run["speculative_config"])
        self.assertEqual(run["kv_cache_dtype"], "fp8_e4m3")
        self.assertEqual(run["graph_mode"], "FULL_AND_PIECEWISE")
        self.assertEqual(run["graph_capture_sizes"], [1, 2])
        self.assertEqual(run["max_cudagraph_capture_size"], 2)
        self.assertEqual(self.manifest["exact_depth_contract"]["depths"], [4096])
        self.assertEqual(self.runner.count("--depth 4096"), 1)
        self.assertNotIn("--depth 2048", self.runner)
        self.assertNotIn("--depth 8192", self.runner)
        self.assertNotIn("for depth in", self.runner)

    def test_preregistered_missing_target_now_resolves_as_one_exact_quarantine(self) -> None:
        contract = self.manifest["coverage_contract"]
        self.assertEqual(contract["id"], "qwen38-tp1-vllm-xpu-target-matrix")
        self.assertEqual(contract["preregistration_state"], "missing")
        family = json.loads(FAMILY.read_text(encoding="utf-8"))
        raw_contract = next(
            item for item in family["coverage_contracts"] if item["id"] == contract["id"]
        )
        module_path = REPO / "tools/build-family-pages.py"
        spec = importlib.util.spec_from_file_location("build_family_pages_for_contract", module_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cells, errors = module.expand_coverage_contract(raw_contract)
        self.assertEqual(errors, [])
        target = next(cell for cell in cells if cell["selectors"] == contract["selectors"])
        rule_id = "quarantined-f01e-autoround-full-and-piecewise-e4m3kv-exact-4k"
        self.assertEqual(target["state"], "quarantined")
        self.assertEqual(target["rule_ids"], ["default-exact-gap", rule_id])
        self.assertNotIn("evidence_id", target)
        self.assertNotIn("point_x", target)
        self.assertNotIn("packet_id", target)
        self.assertIn("no measured speed", target["label"])
        matching = [cell for cell in cells if rule_id in cell["rule_ids"]]
        self.assertEqual(len(matching), 1)
        siblings = [
            cell for cell in cells
            if cell["selectors"]["artifact_id"] == "qwen38-27b-autoround-w4a16-bce40ca"
            and cell["selectors"]["graph_mode"] == "FULL_AND_PIECEWISE"
            and cell["selectors"]["kv"] == "fp8_e4m3"
        ]
        self.assertEqual(len(siblings), 7)
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in siblings if cell["state"] == "missing"],
            [0, 2048, 8192, 16384, 24576, 32768],
        )
        self.assertEqual(contract["other_cells_authorized"], 0)

    def test_dual_e4m3_raw_array_oracles_are_pinned(self) -> None:
        oracles = self.manifest["dual_e4m3_oracles"]
        self.assertEqual(
            oracles["eager"]["exact_4k"]["sha256"],
            "1d541ec78830ba6455b4434c352fe5a44ba5000f5d9d5e6f4c171b7f1053884f",
        )
        self.assertEqual(
            oracles["piecewise"]["exact_4k"]["sha256"],
            "cb4f7c4b0047240b9f01c876e6703211512df3ac2b6bbf2dd5846fa05ad6c528",
        )
        expected = "a3d7ad63a22cfb897d9d7f69952e30e2036617776d18fb4c8a9be1513da522cd"
        self.assertEqual(oracles["eager"]["exact_4k"]["output_token_ids_sha256"], expected)
        self.assertEqual(oracles["piecewise"]["exact_4k"]["output_token_ids_sha256"], expected)
        self.assertIn("candidate_ids == eager_e4m3_ids == piecewise_e4m3_ids", self.runner)
        self.assertIn("candidate_ids == eager_ids == piecewise_ids", self.runner)

    def test_f16_is_comparison_only_not_an_oracle(self) -> None:
        precedent = self.manifest["comparison_only_full_graph_precedent"]
        self.assertEqual(
            precedent["result"]["sha256"],
            "4c3390a42cc1e86b7becef4d9f9a52a8bb2dae937cd8ccecf3180a13366e75b5",
        )
        self.assertIn("do not transfer", precedent["authority"])
        self.assertIn("F16 exact 4K has a different token hash (`3febb16e...`)", self.note)
        target_body = self.runner.split("write_target_verification()", 1)[1].split(
            "write_cache_isolation()", 1
        )[0]
        self.assertNotIn("3febb16e", target_body)

    def test_full_and_piecewise_graph_identity_is_fail_closed(self) -> None:
        for token in (
            "VLLM_XPU_ENABLE_XPU_GRAPH=1",
            'cudagraph_mode\":\"FULL_AND_PIECEWISE',
            'cudagraph_capture_sizes\":[1,2]',
            'max_cudagraph_capture_size\":2',
            "CUDAGraphMode.FULL_AND_PIECEWISE",
            "cudagraph_capture_sizes': [1, 2]",
            "max_cudagraph_capture_size': 2",
            "enforce_eager=False",
            "Capturing CUDA graphs (mixed prefill-decode, PIECEWISE)",
            "Capturing CUDA graphs (decode, FULL)",
            "Graph capturing finished",
        ):
            self.assertIn(token, self.runner)
        self.assertNotIn("--enforce-eager", self.runner)

    def test_tp1_mtp0_and_no_speculation_are_fail_closed(self) -> None:
        for token in (
            "--tensor-parallel-size 1",
            "ZE_AFFINITY_MASK=0",
            "ONEAPI_DEVICE_SELECTOR=level_zero:0",
            "world_size=1 rank=0 local_rank=0",
            "TP rank 0",
            "speculative_config=None",
        ):
            self.assertIn(token, self.runner)
        self.assertNotIn("--speculative-config", self.runner)

    def test_exact_cache_zero_dual_target_and_full_quality_are_required(self) -> None:
        for token in (
            "candidate_exact_passed",
            "dual_e4m3_target_verification_passed",
            "quality_contract_passed",
            "len(exact) == 7",
            'repeat.get("repeats") == 8',
            'len(repeat.get("unique_hashes", [])) == 1',
            'long_context.get("pass") is True',
            "len(comparisons) == 24",
            "len(cache_values) == 16 and all(cache_values)",
            "--require-baseline",
            "target_ok == 1",
            "quality_ok == 1",
        ):
            self.assertIn(token, self.runner)

    def test_model_rank_cache_and_cleanup_are_required(self) -> None:
        for token in (
            "model-verification.json",
            '"$model_verifier" "$model_manifest" "$model"',
            'expected = ["rank_0_0"]',
            "rank-cache-isolation-gate-failed",
            "trap cleanup_on_exit EXIT",
            "trap 'exit 130' INT",
            "trap 'exit 143' TERM",
            "strict_postcleanup",
            "repository must be clean",
            "canonical GPU campaign lock",
            "output root must be ext4",
            "cache root must be ext4",
        ):
            self.assertIn(token, self.runner)

    def test_no_speed_floor_publication_expansion_or_replacement(self) -> None:
        interpretation = self.manifest["interpretation"]
        self.assertIsNone(interpretation["speed_floor"])
        self.assertFalse(interpretation["historical_replacement_allowed"])
        self.assertFalse(interpretation["automatic_publication"])
        self.assertFalse(interpretation["automatic_descendant_expansion"])
        self.assertFalse(interpretation["automatic_descendant_execution"])
        self.assertFalse(interpretation["failed_or_quarantined_speed_publication_allowed"])
        self.assertEqual(interpretation["other_site_or_matrix_cells_authorized"], 0)
        self.assertEqual(
            interpretation["protected_values_unchanged"],
            [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144],
        )

    def test_execution_identity_and_static_modes_are_inert(self) -> None:
        execution = self.manifest["execution"]
        self.assertEqual(execution["port"], 19523)
        self.assertEqual(execution["container"], "q38-f01e-ar-tp1-m0-e4kv-fap-4k-r1")
        self.assertEqual(execution["served_model"], "qwen38-f01e-ar-tp1-m0-e4kv-fap-4k-r1")
        self.assertTrue(execution["default_is_inert"])
        self.assertTrue(execution["fresh_roots_only"])
        for token in ("--check", "--plan", "--execute", '"launch_performed":false'):
            self.assertIn(token, self.runner)
        self.assertEqual(self.runner.count("dockerc run -d"), 1)


if __name__ == "__main__":
    unittest.main()
