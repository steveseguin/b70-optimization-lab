#!/usr/bin/env python3
"""Focused inert tests for the Q8_0-weight/F16-KV HTTP packet."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUNNER_PATH = HERE / "run-20260826-qwen38-q8weights-f16kv-tp1-target-http-depth-quality-r1.py"


def load():
    spec = importlib.util.spec_from_file_location("qwen38_q8weights_f16_packet_tested", RUNNER_PATH)
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

    def test_runtime_fixture_clients_are_sealed_base(self):
        for key in ("runtime", "fixture", "clients"):
            self.assertEqual(self.value[key], self.runner.BASE_VALUE[key])
        self.assertEqual(
            self.value["runtime"]["binary_sha256"],
            "ff2441d012488e3cf7fc537a3e7c1a05fea9159043f3f3a0b257f6647e7c6964",
        )

    def test_existing_raw_and_quality_evidence_are_bound(self):
        self.runner.verify_base(self.runner.load_overlay())
        self.assertEqual(self.value["existing_raw_evidence"]["depths"], list(self.runner.DEPTHS))
        self.assertEqual(self.value["existing_quality_evidence"]["classification"], "service-quality-qualified")

    def test_target_only_f16_argv(self):
        argv = self.runner.Execution(self.runner.merged_manifest(self.value)).server_argv()
        self.assertEqual(argv[argv.index("-m") + 1], self.value["model"]["path"])
        self.assertEqual(argv[argv.index("-ctk") + 1], "f16")
        self.assertEqual(argv[argv.index("-ctv") + 1], "f16")
        self.assertEqual(argv[argv.index("--spec-type") + 1], "none")
        self.assertNotIn("--spec-draft-model", argv)
        self.assertEqual(argv[argv.index("-fit") + 1], "off")
        self.assertEqual(self.value["selectors"]["graph_mode"], "off")

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

    def test_narrow_authority_and_protected_values(self):
        frozen = self.value["frozen_interpretation"]
        self.assertIsNone(frozen["speed_floor"])
        self.assertEqual(frozen["target_only_q8weights_f16_serving_curve_cells_if_all_gates_pass"], 7)
        for key in (
            "other_weight_quantization_cells_authorized",
            "q8_kv_cells_authorized",
            "speculative_cells_authorized",
            "tp2_or_tp4_cells_authorized",
            "graph_cells_authorized",
            "prefill_cells_authorized",
        ):
            self.assertEqual(frozen[key], 0)
        self.assertFalse(frozen["headline_or_protected_replacement_authorized"])
        self.assertEqual(
            frozen["protected_decode_values"],
            [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144],
        )


if __name__ == "__main__":
    unittest.main()
