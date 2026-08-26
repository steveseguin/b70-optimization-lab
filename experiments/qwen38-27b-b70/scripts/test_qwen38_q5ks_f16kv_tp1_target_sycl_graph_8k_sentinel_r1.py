#!/usr/bin/env python3
"""Focused inert tests for the Qwen3.8 Q5 F16-KV graph sentinel packet."""

import importlib.util, json, subprocess, sys, tempfile, unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
RUNNER_PATH=HERE/"run-20260826-qwen38-q5ks-f16kv-tp1-target-sycl-graph-8k-sentinel-r1.py"

def load():
    spec=importlib.util.spec_from_file_location("qwen38_q5_graph_sentinel_tested",RUNNER_PATH); module=importlib.util.module_from_spec(spec); sys.modules[spec.name]=module; spec.loader.exec_module(module); return module

class PacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.r=load(); cls.v=cls.r.load_manifest()
    def test_narrow_authority(self):
        f=self.v["frozen_interpretation"]
        self.assertEqual(f["site_cells_authorized"],0); self.assertTrue(f["sentinel_pass_authorizes_full_curve_preregistration"]); self.assertFalse(f["full_graph_curve_authorized"]); self.assertEqual(f["mtp_or_speculative_cells_authorized"],0); self.assertIsNone(f["speed_floor"])
    def test_exact_arm_delta(self):
        e=self.v["execution_contract"]; self.assertEqual(e["control_environment_delta"],{"GGML_SYCL_ENABLE_GRAPH":"0","GGML_SYCL_GRAPH_CACHE_SIZE":"0"}); self.assertEqual(e["candidate_environment_delta"],{"GGML_SYCL_ENABLE_GRAPH":"1","GGML_SYCL_GRAPH_CACHE_SIZE":"8"}); self.assertFalse(e["candidate_quality_battery"])
    def test_target_only_argv(self):
        argv=self.r.Execution(self.r.graph_manifest(self.v)).server_argv(); self.assertEqual(argv[argv.index("--spec-type")+1],"none"); self.assertNotIn("--spec-draft-model",argv); self.assertEqual(argv[argv.index("-m")+1],self.v["model"]["path"]); self.assertEqual(argv[argv.index("-ctk")+1],"f16"); self.assertEqual(argv[argv.index("-ctv")+1],"f16")
    def test_inert_without_execute(self):
        with tempfile.TemporaryDirectory() as d:
            before=set(Path(d).iterdir()); result=subprocess.run([sys.executable,str(RUNNER_PATH)],cwd=d,text=True,capture_output=True); self.assertEqual(result.returncode,0,result.stderr); self.assertEqual(before,set(Path(d).iterdir())); self.assertTrue(json.loads(result.stdout)["default_is_inert"])
    def test_wrong_ack_cannot_execute(self):
        result=subprocess.run([sys.executable,str(RUNNER_PATH),"--execute","--ack","wrong"],text=True,capture_output=True); self.assertNotEqual(result.returncode,0); self.assertIn("exact --ack required",result.stderr)

if __name__=="__main__": unittest.main()
