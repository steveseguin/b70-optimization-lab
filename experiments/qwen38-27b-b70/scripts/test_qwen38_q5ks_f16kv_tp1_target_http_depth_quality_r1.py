#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUNNER_PATH = HERE / "run-20260826-qwen38-q5ks-f16kv-tp1-target-http-depth-quality-r1.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


R = load(RUNNER_PATH, "qwen38_q5ks_f16_target_depth_test_runner")


class Tests(unittest.TestCase):
    def setUp(self):
        self.overlay = R.load_overlay()
        self.value = R.load_manifest()
        self.base = R.SEALED_BASE_VALUE

    def test_shared_model_runtime_fixture_and_clients_are_exact(self):
        for key in ("model", "runtime", "fixture", "clients"):
            self.assertEqual(self.value[key], self.base[key])
        self.assertEqual(self.value["model"]["sha256"], "d8d62ffcf84d42658dd6ccf9782b4d0404700af78b26d750507510c7597b5bfe")

    def test_delta_is_target_only_f16kv(self):
        argv = R.Execution(R.merged_manifest(self.value)).server_argv()
        self.assertEqual(argv[argv.index("--spec-type") + 1], "none")
        self.assertNotIn("--spec-draft-model", argv)
        self.assertEqual(argv[argv.index("-ctk") + 1], "f16")
        self.assertEqual(argv[argv.index("-ctv") + 1], "f16")
        self.assertEqual(argv[argv.index("-fit") + 1], "off")
        self.assertEqual(self.value["selectors"]["graph_mode"], "off")

    def test_passed_q8_sibling_and_existing_f16_raw_curve_are_bound(self):
        R.verify_base(self.overlay)
        self.assertEqual(self.value["parent"]["required_status"], "completed-valid-target-only-depth-quality")
        self.assertEqual(self.value["existing_f16_evidence"]["depths"], list(R.DEPTHS))

    def test_inert_check_is_complete(self):
        result = subprocess.run(
            [sys.executable, "-B", str(RUNNER_PATH), "--check"],
            check=True, text=True, capture_output=True,
        )
        plan = json.loads(result.stdout)
        self.assertEqual((plan["gpu_actions"], plan["network_requests"], plan["output_writes"]), (0, 0, 0))
        self.assertEqual(plan["depths"], list(R.DEPTHS))
        self.assertEqual(plan["fresh_server_lifetimes"], 1)
        self.assertEqual(plan["quality_batteries"], 1)

    def test_authority_is_only_seven_f16_target_cells(self):
        frozen = self.value["frozen_interpretation"]
        self.assertIsNone(frozen["speed_floor"])
        self.assertEqual(frozen["target_only_f16_serving_curve_cells_if_all_gates_pass"], 7)
        for key in (
            "speculative_cells_authorized", "q8_kv_cells_authorized", "tp2_or_tp4_cells_authorized",
            "graph_cells_authorized", "prefill_cells_authorized",
        ):
            self.assertEqual(frozen[key], 0)
        self.assertFalse(frozen["headline_or_protected_replacement_authorized"])
        self.assertEqual(
            frozen["protected_decode_values"],
            [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144],
        )

    def test_full_quality_contract_is_preserved(self):
        self.assertEqual(self.value["clients"]["quality"], self.base["clients"]["quality"])
        self.assertEqual(self.value["clients"]["quality"]["repeat_runs"], 2)
        self.assertGreaterEqual(self.value["clients"]["quality"]["long_context_tokens"], 27000)


if __name__ == "__main__":
    unittest.main()
