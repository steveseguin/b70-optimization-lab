#!/usr/bin/env python3
"""Focused inert tests for the Q5_K_S cache64 graph curve packet."""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUNNER_PATH = HERE / "run-20260826-qwen38-q5ks-f16kv-tp1-sycl-graph-cache64-depth-quality-r1.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("qwen38_q5ks_graph_curve_tested", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = load_runner()
        cls.overlay = cls.runner.load_overlay()
        cls.value = cls.runner.load_manifest()
        cls.merged = cls.runner.merged_manifest(cls.value)

    def test_exact_q5_model_graph_runtime_and_scope(self):
        self.assertEqual(self.value["model"], self.runner.BASE_VALUE["model"])
        graph_runtime = self.runner.SENTINEL_VALUE["graph_runtime"]
        self.assertEqual(self.value["runtime"]["binary"], graph_runtime["binary"])
        self.assertEqual(self.value["runtime"]["binary_sha256"], graph_runtime["binary_sha256"])
        self.assertEqual(self.value["runtime"]["patch_chain_sha256"], graph_runtime["patch_chain_sha256"])
        self.assertEqual(self.value["selectors"]["active_context_tokens"], [0,2048,4096,8192,16384,24576,32768])
        self.assertEqual(self.value["selectors"]["graph_mode"], "SYCL graph cache64")
        self.assertIsNone(self.value["frozen_interpretation"]["speed_floor"])
        self.assertEqual(self.value["frozen_interpretation"]["protected_decode_values"], [71.45427094575045,30.329809361830037,49.05894025767351,71.9001988117144])

    def test_capacity_choice_and_graph_conservation(self):
        decision = self.value["capacity_decision"]
        self.assertEqual(decision["selected_cache_size"], decision["source_supported_maximum"])
        self.assertEqual(decision["same_workload_cache20_cache_full"], 691)
        self.assertEqual(decision["same_workload_cache64_direct_replays"], 947)
        self.assertTrue(decision["no_further_capacity_escalation"])
        text = "[SYCL-GRAPH] summary device=0 requested=1182 compatibility_rejected=0 device_unsupported=0 cache_entries=64 cache_limit=64 cache_hit=947 cache_miss=235 cache_full=171 direct_replay=947 recorded=64 created=64 updated=0 recreated=0 replayed=1011"
        self.assertEqual(self.runner.parse_graph_evidence(text)["direct_replay"], 947)
        with self.assertRaises(self.runner.GateError):
            self.runner.parse_graph_evidence(text.replace("direct_replay=947", "direct_replay=895"))

    def test_report_composition_and_x0_metadata_preflight(self):
        self.assertEqual(self.merged["zero_context_semantics"]["definition"], "zero prior active context before submitting the minimal explicit prompt token")
        graph = self.runner.parse_graph_evidence("[SYCL-GRAPH] summary device=0 requested=1182 compatibility_rejected=0 device_unsupported=0 cache_entries=64 cache_limit=64 cache_hit=947 cache_miss=235 cache_full=171 direct_replay=947 recorded=64 created=64 updated=0 recreated=0 replayed=1011")
        report = self.runner.compose_terminal_report({"checks":{"base":True,"graph":True},"cells":[{}] * 7}, graph, self.value)
        self.assertEqual(report["status"], "completed-valid-q5ks-f16kv-graph-cache64-depth-quality")
        self.assertEqual(report["graph_evidence"], graph)
        self.assertEqual(report["authority"]["graph_q5ks_f16_serving_curve_cells"], 7)
        self.assertFalse(report["authority"]["protected_or_headline_replacement"])

    def test_inert_default_and_wrong_ack(self):
        with tempfile.TemporaryDirectory() as directory:
            before = set(Path(directory).iterdir())
            result = subprocess.run([sys.executable, str(RUNNER_PATH)], cwd=directory, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(before, set(Path(directory).iterdir()))
            plan = json.loads(result.stdout)
            self.assertEqual(plan["gpu_actions"], 0)
            self.assertEqual(plan["candidate_cache_limit"], 64)
            self.assertTrue(plan["report_composition_preflight"])
            self.assertFalse(plan["further_capacity_escalation"])
        result = subprocess.run([sys.executable, str(RUNNER_PATH), "--execute", "--ack", "wrong"], text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exact --ack required", result.stderr)


if __name__ == "__main__":
    unittest.main()
