#!/usr/bin/env python3
"""Focused inert tests for the Q4_K_XL cache20 graph curve packet."""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


HERE=Path(__file__).resolve().parent
RUNNER_PATH=HERE/"run-20260826-qwen38-q4kxl-f16kv-tp1-sycl-graph-cache20-depth-quality-r1.py"


def load_runner():
    spec=importlib.util.spec_from_file_location("qwen38_q4kxl_graph_curve_tested",RUNNER_PATH); module=importlib.util.module_from_spec(spec); sys.modules[spec.name]=module; spec.loader.exec_module(module); return module


class PacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner=load_runner(); cls.overlay=cls.runner.load_overlay(); cls.value=cls.runner.load_manifest()

    def test_seven_cells_and_narrow_authority(self):
        self.assertEqual(self.value["selectors"]["active_context_tokens"],[0,2048,4096,8192,16384,24576,32768])
        self.assertEqual(self.value["selectors"]["graph_mode"],"SYCL graph cache20")
        frozen=self.value["frozen_interpretation"]
        self.assertEqual(frozen["graph_q4kxl_f16_serving_curve_cells_if_all_gates_pass"],7)
        self.assertEqual(frozen["graph_off_cells_authorized"],0)
        self.assertFalse(frozen["headline_or_protected_replacement_authorized"])
        self.assertIsNone(frozen["speed_floor"])

    def test_graph_conservation_parser(self):
        text="[SYCL-GRAPH] summary device=0 requested=2500 compatibility_rejected=0 device_unsupported=0 cache_entries=20 cache_limit=20 cache_hit=2200 cache_miss=300 cache_full=280 direct_replay=2200 recorded=20 created=20 updated=0 recreated=0 replayed=2220"
        graph=self.runner.parse_graph_evidence(text)
        self.assertEqual(graph["direct_replay"],2200); self.assertEqual(graph["cache_full"],280)
        with self.assertRaises(self.runner.GateError): self.runner.parse_graph_evidence(text.replace("direct_replay=2200","direct_replay=2199"))

    def test_inert_default_and_wrong_ack(self):
        with tempfile.TemporaryDirectory() as directory:
            before=set(Path(directory).iterdir()); result=subprocess.run([sys.executable,str(RUNNER_PATH)],cwd=directory,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr); self.assertEqual(before,set(Path(directory).iterdir())); plan=json.loads(result.stdout)
            self.assertEqual(plan["gpu_actions"],0); self.assertEqual(plan["graph_q4kxl_f16_cells_if_valid"],7)
        result=subprocess.run([sys.executable,str(RUNNER_PATH),"--execute","--ack","wrong"],text=True,capture_output=True)
        self.assertNotEqual(result.returncode,0); self.assertIn("exact --ack required",result.stderr)


if __name__=="__main__":
    unittest.main()
