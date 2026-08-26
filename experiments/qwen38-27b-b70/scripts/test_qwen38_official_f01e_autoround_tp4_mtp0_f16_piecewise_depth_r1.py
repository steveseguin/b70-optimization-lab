#!/usr/bin/env python3
"""Inert contract tests for current-f01e TP4/MTP0 PIECEWISE depth R1."""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import tempfile
import unittest


REPO = pathlib.Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-26-qwen38-official-f01e-autoround-tp4-mtp0-f16-piecewise-depth-r1-prereg.json"
NOTE = LANE / "notes/2026-08-26-qwen38-official-f01e-autoround-tp4-mtp0-f16-piecewise-depth-r1-preregistration.md"
RUNNER = LANE / "scripts/run-20260826-qwen38-official-f01e-autoround-tp4-mtp0-f16-piecewise-depth-r1.sh"
DEPTHS = [2048, 4096, 8192, 16384, 24576, 32768]
PROTECTED = [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144]


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text())
        cls.note = NOTE.read_text()
        cls.runner = RUNNER.read_text()

    def test_exact_current_f01e_tp4_piecewise_identity(self) -> None:
        run = self.manifest["run_identity"]
        self.assertEqual((run["tensor_parallel"], run["mtp_depth"]), (4, 0))
        self.assertEqual(run["gpu_affinity"], "0,1,2,3")
        self.assertEqual(run["graph_mode"], "PIECEWISE")
        self.assertEqual(run["graph_capture_sizes"], [1])
        self.assertEqual(run["kv_cache_dtype"], "float16")
        self.assertIsNone(run["speculative_config"])
        self.assertIn("--tensor-parallel-size 4", self.runner)
        self.assertIn('cudagraph_mode":"PIECEWISE', self.runner)
        self.assertNotIn("--enforce-eager", self.runner)
        self.assertNotIn("--speculative-config", self.runner)

    def test_six_exact_depths_one_server(self) -> None:
        self.assertEqual(self.manifest["exact_depth_contract"]["depths"], DEPTHS)
        self.assertEqual(self.runner.count("dockerc run -d"), 1)
        self.assertIn('for depth in "${depths[@]}"', self.runner)
        self.assertTrue(self.manifest["execution"]["one_server_lifetime"])

    def test_current_eager_oracle_is_required_and_dated_graph_is_caveat(self) -> None:
        parents = self.manifest["parent_oracles"]
        self.assertEqual(
            parents["same_image_same_topology_eager"]["terminal_state"],
            "passed-quality-clean-depth-expansion-with-comparison-caveat",
        )
        self.assertIn("All six candidate outputs must exactly match", parents["same_image_same_topology_eager"]["gate"])
        self.assertIn("caveat", parents["dated_graph_comparison"]["policy"])
        self.assertIn("same_image_target_comparison", self.runner)
        self.assertIn("dated_graph_comparison", self.runner)
        self.assertNotIn("dated_passes == 6", self.runner)

    def test_current_eager_and_dated_receipts_are_exactly_pinned(self) -> None:
        parents = self.manifest["parent_oracles"]
        eager = parents["same_image_same_topology_eager"]
        dated = parents["dated_graph_comparison"]
        self.assertEqual(eager["terminal_receipt_sha256"], "f6ed578228a9e6c21c68653b828a0ecc4ee776107337446e6ecc2f595d47297e")
        self.assertEqual(eager["arm_result_sha256"], "f9d6aac74557a16dc3da1f55f2d9da76908cac17b341fb1abc2fd55fbb1f4414")
        self.assertEqual(eager["quality_sha256"], "2172c3bdba148062487ba73980fee46a5f1f2501baa37ceb83ca0e058bcaa83f")
        self.assertEqual(dated["result_sha256"], "ff64abc91423519b529a5c924e9c5c59ee75e5b203cfe0d594297a30b19d8fbc")
        eager_receipts = self.manifest["exact_depth_contract"]["same_image_target_receipt_sha256"]
        dated_receipts = self.manifest["exact_depth_contract"]["dated_graph_receipt_sha256"]
        self.assertEqual(set(eager_receipts), {str(depth) for depth in DEPTHS})
        self.assertEqual(set(dated_receipts), {str(depth) for depth in DEPTHS})
        for digest in [eager["terminal_receipt_sha256"], eager["arm_result_sha256"],
                       eager["quality_sha256"], dated["result_sha256"],
                       *eager_receipts.values(), *dated_receipts.values()]:
            self.assertIn(digest, self.runner)

    def test_full_quality_graph_topology_cache_and_cleanup_gates(self) -> None:
        for token in (
            "Capturing CUDA graphs (mixed prefill-decode, PIECEWISE)",
            "Graph capturing finished",
            "Capturing CUDA graphs (decode, FULL)",
            "world_size=4, local_world_size=4",
            'expected = ["rank_0_0", "rank_1_0", "rank_2_0", "rank_3_0"]',
            "quality_objective_gate",
            "baseline_match_all",
            "strict_postcleanup",
        ):
            self.assertIn(token, self.runner)
        self.assertEqual(self.runner.count("ZE_AFFINITY_MASK=0,1,2,3"), 1)
        self.assertIn('"tp4_worker_topology_passed": topology_ok == "1"', self.runner)

    def test_protected_and_publication_boundaries(self) -> None:
        interpretation = self.manifest["interpretation"]
        self.assertEqual(interpretation["protected_decode_values_unchanged"], PROTECTED)
        self.assertFalse(interpretation["historical_replacement_allowed"])
        self.assertFalse(interpretation["eager_profile_replacement_allowed"])
        self.assertFalse(interpretation["dated_graph_profile_replacement_allowed"])
        self.assertFalse(interpretation["automatic_publication_allowed"])
        self.assertFalse(interpretation["descendant_execution_authorized"])
        self.assertEqual(interpretation["site_cells_filled_automatically"], 0)
        self.assertEqual(interpretation["measured_cells_on_full_pass"], 6)
        self.assertIsNone(interpretation["speed_floor"])

    def test_context_zero_is_missing(self) -> None:
        contract = self.manifest["exact_depth_contract"]
        self.assertEqual(contract["depth_zero_state"], "missing")
        self.assertNotIn(0, contract["depths"])
        self.assertIn("Context zero remains missing", self.note)

    def test_runner_is_inert_fresh_and_unique(self) -> None:
        execution = self.manifest["execution"]
        self.assertTrue(execution["default_is_inert"])
        self.assertTrue(execution["fresh_roots_only"])
        self.assertEqual(execution["port"], 19498)
        self.assertIn("exact acknowledgement required", self.runner)
        self.assertIn('[[ ! -e "$root" ]]', self.runner)
        self.assertIn('[[ ! -e "$cache_root" ]]', self.runner)

    def test_result_writer_never_auto_publishes(self) -> None:
        match = re.search(r"write_arm_result\(\) \{.*?<<'PY'\n(.*?)\nPY\n\}", self.runner, re.DOTALL)
        self.assertIsNotNone(match)
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "exact-depth").mkdir()
            (root / "verification").mkdir()
            for depth in DEPTHS:
                (root / "exact-depth" / f"depth-{depth}.rc").write_text("0\n")
                (root / "verification" / f"depth-{depth}.json").write_text(json.dumps({"same_image_target_comparison": {"passed": True}}))
            output = root / "arm-result.json"
            args = [str(output), "passed-quality-clean-piecewise-depth", "test", "6", "6", "6", "0", "1", "0", "1", "1", "1", "1", "1", str(root)]
            completed = subprocess.run(["python3", "-c", match.group(1), *args], text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(output.read_text())
            self.assertFalse(result["automatic_publication_allowed"])
            self.assertFalse(result["historical_or_protected_replacement_allowed"])
            self.assertFalse(result["descendant_execution_authorized"])
            self.assertTrue(result["tp4_worker_topology_passed"])
            self.assertEqual(result["valid_depths"], DEPTHS)


if __name__ == "__main__":
    unittest.main()
