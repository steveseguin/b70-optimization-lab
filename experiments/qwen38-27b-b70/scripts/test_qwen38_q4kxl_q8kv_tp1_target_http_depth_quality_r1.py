#!/usr/bin/env python3
"""Focused inert tests for the UD-Q4_K_XL/Q8_0-KV HTTP packet."""

import importlib.util, json, subprocess, sys, tempfile, unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
RUNNER_PATH=HERE/"run-20260826-qwen38-q4kxl-q8kv-tp1-target-http-depth-quality-r1.py"

def load():
    spec=importlib.util.spec_from_file_location("qwen38_q4kxl_q8_packet_tested",RUNNER_PATH); module=importlib.util.module_from_spec(spec); sys.modules[spec.name]=module; spec.loader.exec_module(module); return module

class PacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.r=load(); cls.v=cls.r.load_manifest()
    def test_exact_artifact(self):
        self.assertEqual(self.v["model"]["sha256"],"3f227079003add2511437e5b1e94812e363385225bf6a9b47b0054a72bc8b01e"); self.assertEqual(self.v["selectors"]["target_quantization"],"UD-Q4_K_XL")
    def test_narrow_authority(self):
        f=self.v["frozen_interpretation"]; self.assertEqual(f["target_only_q4kxl_q8kv_serving_curve_cells_if_all_gates_pass"],7); self.assertIsNone(f["speed_floor"]); self.assertEqual(f["f16_kv_cells_authorized"],0); self.assertEqual(f["speculative_cells_authorized"],0); self.assertEqual(f["graph_cells_authorized"],0)
    def test_target_only_q8_argv(self):
        argv=self.r.Execution(self.r.merged_manifest(self.v)).server_argv(); self.assertEqual(argv[argv.index("-m")+1],self.v["model"]["path"]); self.assertEqual(argv[argv.index("-ctk")+1],"q8_0"); self.assertEqual(argv[argv.index("-ctv")+1],"q8_0"); self.assertEqual(argv[argv.index("--spec-type")+1],"none"); self.assertEqual(argv[argv.index("-fit")+1],"off")
    def test_parent_is_exact_passed_f16_sibling(self):
        base=self.v["parent"]; self.assertEqual(base["required_status"],"completed-valid-target-only-q4kxl-f16kv-depth-quality"); self.assertEqual(base["terminal_sha256"],"7686c8e460e3a45a81b625833b561de091e4db3fd0c2b3fac2f2cbbaca26731c")
    def test_default_inert(self):
        with tempfile.TemporaryDirectory() as d:
            before=set(Path(d).iterdir()); result=subprocess.run([sys.executable,str(RUNNER_PATH)],cwd=d,text=True,capture_output=True); self.assertEqual(result.returncode,0,result.stderr); self.assertEqual(before,set(Path(d).iterdir())); self.assertTrue(json.loads(result.stdout)["default_is_inert"])
    def test_wrong_ack_rejected(self):
        result=subprocess.run([sys.executable,str(RUNNER_PATH),"--execute","--ack","wrong"],text=True,capture_output=True); self.assertNotEqual(result.returncode,0); self.assertIn("exact --ack required",result.stderr)

if __name__=="__main__": unittest.main()
