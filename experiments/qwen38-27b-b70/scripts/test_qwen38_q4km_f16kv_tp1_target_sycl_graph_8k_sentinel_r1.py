#!/usr/bin/env python3
"""Focused inert tests for the Qwen3.8 Q4_K_M/F16 graph sentinel."""
import importlib.util,json,subprocess,sys,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent; RUNNER=HERE/"run-20260826-qwen38-q4km-f16kv-tp1-target-sycl-graph-8k-sentinel-r1.py"; VALIDATOR=HERE/"validate-20260826-qwen38-q4km-f16kv-tp1-target-sycl-graph-8k-sentinel-r1.py"
def load():
    spec=importlib.util.spec_from_file_location("qwen38_q4km_graph_sentinel_tested",RUNNER); module=importlib.util.module_from_spec(spec); sys.modules[spec.name]=module; spec.loader.exec_module(module); return module
class PacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.r=load(); cls.v=cls.r.load_manifest()
    def test_narrow_authority(self):
        f=self.v["frozen_interpretation"]; self.assertEqual(f["site_cells_authorized"],0); self.assertTrue(f["sentinel_pass_authorizes_full_curve_preregistration"]); self.assertFalse(f["full_graph_curve_authorized"]); self.assertIsNone(f["speed_floor"])
    def test_exact_arm_delta(self):
        e=self.v["execution_contract"]; self.assertEqual(e["control_environment_delta"],{"GGML_SYCL_ENABLE_GRAPH":"0","GGML_SYCL_GRAPH_CACHE_SIZE":"0"}); self.assertEqual(e["candidate_environment_delta"],{"GGML_SYCL_ENABLE_GRAPH":"1","GGML_SYCL_GRAPH_CACHE_SIZE":"20"}); self.assertTrue(e["require_positive_graph_requests_hits_and_direct_replay"]); self.assertEqual(e["require_minimum_cache_hits_and_direct_replays"],120); self.assertTrue(e["no_automatic_capacity_escalation"])
    def test_target_only_q4km_argv(self):
        argv=self.r.Execution(self.r.graph_manifest(self.v)).server_argv(); self.assertEqual(argv[argv.index("-m")+1],self.v["model"]["path"]); self.assertEqual(argv[argv.index("--spec-type")+1],"none"); self.assertNotIn("--spec-draft-model",argv); self.assertEqual(argv[argv.index("-ctk")+1],"f16"); self.assertEqual(argv[argv.index("-ctv")+1],"f16")
    def test_validator_requires_real_reuse_and_no_cache_full(self):
        text=VALIDATOR.read_text(encoding="utf-8"); self.assertIn('graph.get("cache_hit",0)>=120',text); self.assertIn('graph.get("direct_replay",0)>=120',text); self.assertIn('("cache_full","compatibility_rejected","device_unsupported","updated","recreated")',text)
    def test_default_inert(self):
        with tempfile.TemporaryDirectory() as d:
            before=set(Path(d).iterdir()); result=subprocess.run([sys.executable,str(RUNNER)],cwd=d,text=True,capture_output=True); self.assertEqual(result.returncode,0,result.stderr); self.assertEqual(before,set(Path(d).iterdir())); self.assertTrue(json.loads(result.stdout)["default_is_inert"])
    def test_wrong_ack_rejected(self):
        result=subprocess.run([sys.executable,str(RUNNER),"--execute","--ack","wrong"],text=True,capture_output=True); self.assertNotEqual(result.returncode,0); self.assertIn("exact --ack required",result.stderr)
if __name__=="__main__": unittest.main()
