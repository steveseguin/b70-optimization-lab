#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUNNER_PATH = HERE / "run-20260825-qwen38-q5ks-q8kv-tp1-target-http-depth-quality-r1.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


R = load(RUNNER_PATH, "qwen38_q5ks_target_depth_test_runner")


class Tests(unittest.TestCase):
    def setUp(self):
        self.value = R.load_manifest()
        self.merged = R.merged_manifest(self.value)

    def test_exact_current_identity(self):
        self.assertEqual(self.value["model"]["sha256"], "d8d62ffcf84d42658dd6ccf9782b4d0404700af78b26d750507510c7597b5bfe")
        self.assertEqual(self.value["runtime"]["source_commit"], "9fee29e9435f865ec0b811a783a6471a136d9317")
        self.assertEqual(self.value["parent"]["required_control_output_token_ids_sha256"], "e2f7a659a1b9fc93aeb8b766be5ceb4b9c9f835ad61b50023a0224401eed141c")

    def test_target_only_q8kv_graph_and_fit_off(self):
        argv = R.Execution(self.merged).server_argv()
        self.assertEqual(argv[argv.index("--spec-type") + 1], "none")
        self.assertNotIn("--spec-draft-model", argv)
        self.assertEqual(argv[argv.index("-ctk") + 1], "q8_0")
        self.assertEqual(argv[argv.index("-ctv") + 1], "q8_0")
        self.assertEqual(argv[argv.index("-fit") + 1], "off")

    def test_inert_check_is_complete(self):
        result = subprocess.run([sys.executable, "-B", str(RUNNER_PATH), "--check"], check=True, text=True, capture_output=True)
        plan = json.loads(result.stdout)
        self.assertEqual((plan["gpu_actions"], plan["network_requests"], plan["output_writes"]), (0, 0, 0))
        self.assertEqual(plan["depths"], [0, 2048, 4096, 8192, 16384, 24576, 32768])
        self.assertEqual(plan["fresh_server_lifetimes"], 1)
        self.assertEqual(plan["quality_batteries"], 1)

    def test_authority_cannot_replace_protected_or_add_other_cells(self):
        frozen = self.value["frozen_interpretation"]
        self.assertIsNone(frozen["speed_floor"])
        self.assertEqual(frozen["target_only_serving_curve_cells_if_all_gates_pass"], 7)
        self.assertEqual(frozen["speculative_cells_authorized"], 0)
        self.assertEqual(frozen["tp2_or_tp4_cells_authorized"], 0)
        self.assertFalse(frozen["headline_or_protected_replacement_authorized"])

    def test_full_qwen38_quality_helper(self):
        helper = load(R.REPO / self.value["clients"]["quality"]["path"], "qwen38_quality_helper_for_target_depth_test")
        self.assertEqual(len(helper.make_exact_cases()), 7)
        self.assertEqual(self.value["clients"]["quality"]["repeat_runs"], 2)
        self.assertGreaterEqual(self.value["clients"]["quality"]["long_context_tokens"], 27000)


if __name__ == "__main__":
    unittest.main()
