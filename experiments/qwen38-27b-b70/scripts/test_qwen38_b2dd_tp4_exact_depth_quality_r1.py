#!/usr/bin/env python3
"""Focused inert tests for the b2dd/1e90 TP4 exact-depth packet."""

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock


HERE = Path(__file__).resolve().parent
RUNNER_PATH = HERE / "run-20260826-qwen38-b2dd9ce73d-tp4-exact-depth-quality-r1.py"
VALIDATOR_PATH = HERE / "validate-20260826-qwen38-b2dd9ce73d-tp4-exact-depth-quality-r1.py"


def load():
    spec = importlib.util.spec_from_file_location("qwen38_b2dd_tp4_exact_depth_tested", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = load()
        cls.manifest = cls.runner.load_json(cls.runner.MANIFEST)

    def test_dependencies_and_qualified_parent(self):
        observed = self.runner.verify_dependencies()
        self.assertEqual(observed[str(self.runner.RECOVERY)], "728425d919b735ddf86199d568ecc3d7966007b5d234b9c68fafb4ae439fd37a")

    def test_topology_graph_memory_and_source_are_exact(self):
        run = self.manifest["run_identity"]
        self.assertEqual(run["tensor_parallel_size"], 4)
        self.assertEqual(run["gpu_affinity"], "0,1,2,3")
        self.assertEqual(run["gpu_memory_utilization"], 0.6)
        self.assertEqual(run["max_model_len"], 32896)
        self.assertEqual(run["graph_mode"], "FULL_AND_PIECEWISE")
        self.assertEqual(run["vllm_head"], self.runner.VLLM_HEAD)
        self.assertEqual(run["xpu_kernel_head"], self.runner.KERNEL_HEAD)
        self.assertEqual(run["source_overlay"], "none")
        self.assertEqual(run["decision_overlay"], "none")

    def test_stage_environment_is_tp4_fit_and_graph_exact(self):
        env = self.runner.stage_environment()
        self.assertEqual(env["GPU_MEM_UTIL"], "0.60")
        self.assertEqual(env["VLLM_XPU_GRAPH"], "1")
        self.assertEqual(env["REQUIRE_GRAPH_CAPTURE"], "1")
        self.assertNotIn("PYTHONHASHSEED", env)
        self.assertEqual(env["QUALITY_BASELINE_JSON"], str(self.runner.BASELINE))
        extra = json.loads(env["EXTRA_VLLM_ARGS_JSON"])
        config = json.loads(extra[extra.index("--compilation-config") + 1])
        self.assertEqual(config["cudagraph_mode"], "FULL_AND_PIECEWISE")
        self.assertEqual(config["cudagraph_capture_sizes"], [1, 2])

    def test_x0_is_honestly_missing_and_six_cells_only(self):
        contract = self.manifest["exact_depth_contract"]
        frozen = self.manifest["frozen_interpretation"]
        self.assertEqual(contract["measured_depths"], list(self.runner.DEPTHS))
        self.assertEqual(contract["depth_zero"]["state_after_campaign"], "missing")
        self.assertTrue(contract["configured_capacity_is_not_active_context"])
        self.assertEqual(frozen["nonzero_exact_context_cells_authorized_if_all_gates_pass"], 6)
        self.assertEqual(frozen["depth_zero_cells_authorized"], 0)
        self.assertIsNone(frozen["speed_floor"])

    def test_plan_is_inert_and_create_only(self):
        plan = self.runner.plan_payload(1)
        self.assertTrue(plan["default_is_inert"])
        self.assertEqual(plan["gpu_actions"], 0)
        self.assertEqual(plan["tp"], 4)
        self.assertEqual(plan["gpus"], [0, 1, 2, 3])
        self.assertEqual(plan["depth_zero_state"], "missing")
        self.assertIsNone(plan["speed_floor"])
        locks = self.manifest["lifecycle"]["required_locks"]
        self.assertEqual(sum(path.endswith(f"gpu{index}.lock") for path in locks for index in range(4)), 4)

    def test_wrong_ack_stops_before_dependencies_or_gpu(self):
        with mock.patch.object(self.runner, "verify_dependencies") as dependencies:
            with self.assertRaises(self.runner.CampaignError):
                self.runner.execute(1, "wrong")
        dependencies.assert_not_called()

    def test_check_is_inert(self):
        result = subprocess.run([sys.executable, str(RUNNER_PATH), "--check"], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "PASS")
        self.assertFalse(payload["launch_performed"])

    def test_validator_requires_worker_count_quality_cleanup_and_narrow_authority(self):
        text = VALIDATOR_PATH.read_text(encoding="utf-8")
        for needle in ("worker_ranks", "full_quality", "post_cleanup_passed", "depth_zero_cells", "configured_capacity_not_cell"):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
