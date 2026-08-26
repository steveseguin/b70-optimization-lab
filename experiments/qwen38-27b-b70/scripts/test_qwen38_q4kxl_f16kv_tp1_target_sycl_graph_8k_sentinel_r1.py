#!/usr/bin/env python3
"""Focused inert tests for the Qwen3.8 Q4_K_XL/F16 graph sentinel."""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUNNER_PATH = HERE / "run-20260826-qwen38-q4kxl-f16kv-tp1-target-sycl-graph-8k-sentinel-r1.py"
VALIDATOR_PATH = HERE / "validate-20260826-qwen38-q4kxl-f16kv-tp1-target-sycl-graph-8k-sentinel-r1.py"


def load():
    spec = importlib.util.spec_from_file_location("qwen38_q4kxl_graph_sentinel_tested", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = load()
        cls.value = cls.runner.load_manifest()

    def test_narrow_fail_closed_authority(self):
        frozen = self.value["frozen_interpretation"]
        self.assertEqual(frozen["site_cells_authorized"], 0)
        self.assertTrue(frozen["sentinel_pass_authorizes_full_curve_preregistration"])
        self.assertFalse(frozen["full_graph_curve_authorized"])
        self.assertTrue(frozen["failure_stops_same_design_full_curve"])
        self.assertEqual(frozen["mtp_or_speculative_cells_authorized"], 0)
        self.assertIsNone(frozen["speed_floor"])

    def test_exact_arm_delta_and_mechanism_requirements(self):
        execution = self.value["execution_contract"]
        self.assertEqual(
            execution["control_environment_delta"],
            {"GGML_SYCL_ENABLE_GRAPH": "0", "GGML_SYCL_GRAPH_CACHE_SIZE": "0"},
        )
        self.assertEqual(
            execution["candidate_environment_delta"],
            {"GGML_SYCL_ENABLE_GRAPH": "1", "GGML_SYCL_GRAPH_CACHE_SIZE": "20"},
        )
        self.assertTrue(execution["require_positive_graph_requests_hits_and_direct_replay"])
        self.assertTrue(execution["require_zero_graph_compatibility_device_cache_full_update_or_recreate_events"])
        self.assertFalse(execution["candidate_quality_battery"])

    def test_q5_negative_is_sealed_warning(self):
        self.runner.verify_dependencies(self.value)
        warning = self.value["frozen_interpretation"]["known_q5_same_runtime_warning"]
        self.assertIn("zero hits/direct replay", warning)
        self.assertIn("failure closes", warning)

    def test_target_only_q4kxl_argv(self):
        argv = self.runner.Execution(self.runner.graph_manifest(self.value)).server_argv()
        self.assertEqual(argv[argv.index("--spec-type") + 1], "none")
        self.assertNotIn("--spec-draft-model", argv)
        self.assertEqual(argv[argv.index("-m") + 1], self.value["model"]["path"])
        self.assertEqual(argv[argv.index("-ctk") + 1], "f16")
        self.assertEqual(argv[argv.index("-ctv") + 1], "f16")
        self.assertNotIn("-fit", argv)

    def test_validator_requires_positive_hits_and_no_cache_full(self):
        text = VALIDATOR_PATH.read_text(encoding="utf-8")
        self.assertIn('graph.get("cache_hit", 0) >= 120', text)
        self.assertIn('graph.get("direct_replay", 0) >= 120', text)
        self.assertIn('("cache_full", "compatibility_rejected", "device_unsupported", "updated", "recreated")', text)

    def test_inert_without_execute(self):
        with tempfile.TemporaryDirectory() as directory:
            before = set(Path(directory).iterdir())
            result = subprocess.run(
                [sys.executable, str(RUNNER_PATH)], cwd=directory, text=True, capture_output=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(before, set(Path(directory).iterdir()))
            plan = json.loads(result.stdout)
            self.assertTrue(plan["default_is_inert"])
            self.assertEqual(plan["gpu_actions"], 0)
            self.assertEqual(plan["site_cells_if_valid"], 0)

    def test_wrong_ack_cannot_execute(self):
        result = subprocess.run(
            [sys.executable, str(RUNNER_PATH), "--execute", "--ack", "wrong"],
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exact --ack required", result.stderr)


if __name__ == "__main__":
    unittest.main()
