#!/usr/bin/env python3
"""Focused inert tests for the Q4_K_XL graph curve R2 wrapper."""
import importlib.util,json,subprocess,sys,tempfile,unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent; RUNNER_PATH=HERE/"run-20260826-qwen38-q4kxl-f16kv-tp1-sycl-graph-cache20-depth-quality-r2.py"
def load_runner():
    spec=importlib.util.spec_from_file_location("qwen38_q4kxl_graph_curve_r2_tested",RUNNER_PATH); module=importlib.util.module_from_spec(spec); sys.modules[spec.name]=module; spec.loader.exec_module(module); return module

class PacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.runner=load_runner(); cls.value=cls.runner.load_manifest(); cls.merged=cls.runner.merged_manifest(cls.value)
    def test_only_missing_metadata_is_added(self):
        self.assertEqual(cls_semantics:=self.merged["zero_context_semantics"],self.runner.ZERO_CONTEXT_SEMANTICS); self.assertEqual(cls_semantics["definition"],"zero prior active context before submitting the minimal explicit prompt token")
        self.assertEqual(self.value["selectors"],self.runner.R1_VALUE["selectors"]); self.assertEqual(self.value["runtime"],self.runner.R1_VALUE["runtime"]); self.assertEqual(self.value["graph_acceptance"],self.runner.R1_VALUE["graph_acceptance"])
    def test_failed_r1_is_bound_and_clean(self):
        failure=self.runner.load_overlay()["preserved_r1_failure"]; self.assertEqual(failure["measurement_requests_sent"],0); self.assertTrue(failure["clean_shutdown"]); self.assertTrue(failure["must_remain_immutable"])
    def test_inert_default(self):
        with tempfile.TemporaryDirectory() as directory:
            before=set(Path(directory).iterdir()); result=subprocess.run([sys.executable,str(RUNNER_PATH)],cwd=directory,text=True,capture_output=True); self.assertEqual(result.returncode,0,result.stderr); self.assertEqual(before,set(Path(directory).iterdir())); plan=json.loads(result.stdout); self.assertTrue(plan["zero_context_semantics_added"]); self.assertEqual(plan["gpu_actions"],0)

if __name__=="__main__": unittest.main()
