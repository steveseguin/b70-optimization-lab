#!/usr/bin/env python3
"""Focused inert tests for the Q8_0-weight/Q8_0-KV HTTP packet."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUNNER_PATH = HERE / "run-20260826-qwen38-q8weights-q8kv-tp1-target-http-depth-quality-r1.py"


def load():
    spec = importlib.util.spec_from_file_location("qwen38_q8weights_q8kv_packet_tested", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = load()
        cls.value = cls.runner.load_manifest()

    def test_exact_artifact_and_revision(self):
        self.assertEqual(
            self.value["model"]["sha256"],
            "f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8",
        )
        self.assertEqual(self.value["model"]["revision"], "0669b98607d47046c7c2b3f801011d54a08cfccf")
        self.assertEqual(self.value["selectors"]["target_quantization"], "Q8_0")

    def test_parent_is_exact_q8weights_f16_packet(self):
        self.runner.verify_base(self.runner.load_overlay())
        parent = self.value["parent"]
        self.assertEqual(
            parent["manifest_sha256"],
            "0b7c32f75ff54c52cb908a62b614f185dcc5b3f1716abff08edade01b2a67c74",
        )
        self.assertEqual(parent["required_state"], "preregistered-not-launched")
        for key in ("runtime", "fixture", "clients", "model", "model_manifest"):
            self.assertEqual(self.value[key], self.runner.BASE_VALUE[key])

    def test_only_effective_selector_delta_is_q8_kv(self):
        argv = self.runner.Execution(self.runner.merged_manifest(self.value)).server_argv()
        base_argv = self.runner.BASE_EXECUTION(
            self.runner.BASE.merged_manifest(self.runner.BASE_VALUE)
        ).server_argv()
        self.assertEqual(argv[argv.index("-m") + 1], self.value["model"]["path"])
        self.assertEqual(argv[argv.index("-ctk") + 1], "q8_0")
        self.assertEqual(argv[argv.index("-ctv") + 1], "q8_0")
        self.assertEqual(argv[argv.index("--spec-type") + 1], "none")
        self.assertNotIn("--spec-draft-model", argv)
        self.assertEqual(argv[argv.index("-fit") + 1], "off")
        for flag in ("-ctk", "-ctv"):
            base_argv[base_argv.index(flag) + 1] = "q8_0"
        base_argv[base_argv.index("--alias") + 1] = self.value["server_contract"]["model_alias"]
        self.assertEqual(argv, base_argv)

    def test_runtime_fixture_clients_are_sealed(self):
        self.assertEqual(
            self.value["runtime"]["binary_sha256"],
            "ff2441d012488e3cf7fc537a3e7c1a05fea9159043f3f3a0b257f6647e7c6964",
        )
        self.assertEqual(self.value["selectors"]["active_context_tokens"], list(self.runner.DEPTHS))
        self.assertEqual(self.value["execution_contract"]["completion_tokens_per_depth"], 128)
        self.assertTrue(self.value["execution_contract"]["quality_after_all_depths"])
        self.assertTrue(self.value["execution_contract"]["require_cached_tokens_zero_everywhere"])

    def test_default_is_inert_and_reports_storage_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            before = set(Path(directory).iterdir())
            result = subprocess.run(
                [sys.executable, "-B", str(RUNNER_PATH)],
                cwd=directory,
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertEqual(before, set(Path(directory).iterdir()))
        plan = json.loads(result.stdout)
        self.assertEqual((plan["gpu_actions"], plan["network_requests"], plan["output_writes"]), (0, 0, 0))
        self.assertEqual(plan["depths"], list(self.runner.DEPTHS))
        self.assertEqual(plan["quality_batteries"], 1)
        present, disposition = self.runner.model_presence(self.value)
        self.assertEqual(plan["model_present_and_exact_size"], present)
        self.assertEqual(plan["model_preflight"], disposition)
        self.assertEqual(plan["launch_ready"], present)

    def test_wrong_ack_is_inert_and_rejected(self):
        output_root = Path(self.value["lifecycle"]["output_root"])
        existed = output_root.exists()
        result = subprocess.run(
            [sys.executable, "-B", str(RUNNER_PATH), "--execute", "--ack", "wrong"],
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exact --ack required", result.stderr)
        self.assertEqual(output_root.exists(), existed)

    def test_narrow_authority_and_protected_values(self):
        frozen = self.value["frozen_interpretation"]
        self.assertIsNone(frozen["speed_floor"])
        self.assertEqual(frozen["target_only_q8weights_q8kv_serving_curve_cells_if_all_gates_pass"], 7)
        for key in (
            "f16_kv_cells_authorized",
            "other_weight_quantization_cells_authorized",
            "speculative_cells_authorized",
            "tp2_or_tp4_cells_authorized",
            "graph_cells_authorized",
            "prefill_cells_authorized",
        ):
            self.assertEqual(frozen[key], 0)
        self.assertTrue(frozen["estimate_replacement_authorized_only_for_exact_same_selectors"])
        self.assertFalse(frozen["headline_or_protected_replacement_authorized"])
        self.assertEqual(
            frozen["protected_decode_values"],
            [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144],
        )


if __name__ == "__main__":
    unittest.main()
