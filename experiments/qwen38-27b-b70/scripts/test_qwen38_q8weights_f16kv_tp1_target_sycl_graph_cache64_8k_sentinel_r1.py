#!/usr/bin/env python3
"""Focused inert tests for the Q8/F16 cache64 graph sentinel."""
import importlib.util,json,subprocess,sys,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent; RUNNER=HERE/"run-20260826-qwen38-q8weights-f16kv-tp1-target-sycl-graph-cache64-8k-sentinel-r1.py"
def load():
    spec=importlib.util.spec_from_file_location("q8_graph_sentinel_tested",RUNNER); m=importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; spec.loader.exec_module(m); return m
class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.r=load(); cls.v=cls.r.load_manifest()
    def test_authority(self):
        f=self.v["frozen_interpretation"]; self.assertEqual(f["site_cells_authorized"],0); self.assertTrue(f["sentinel_pass_authorizes_separate_seven_depth_full_curve_preregistration"]); self.assertFalse(f["full_graph_curve_authorized"]); self.assertIsNone(f["speed_floor"])
    def test_cache64_is_evidence_derived(self):
        c=self.v["capacity_decision"]; self.assertEqual(c["selected_cache_size"],64); self.assertEqual(c["source_supported_maximum"],64); self.assertTrue(c["no_further_capacity_escalation"]); self.assertEqual([(x["requested"],x["direct_replay"]) for x in c["full_workload_replicas"]],[(1182,947)]*3)
    def test_exact_arm_delta_and_quality(self):
        e=self.v["execution_contract"]; self.assertEqual(e["control_environment_delta"],{"GGML_SYCL_ENABLE_GRAPH":"0","GGML_SYCL_GRAPH_CACHE_SIZE":"0"}); self.assertEqual(e["candidate_environment_delta"],{"GGML_SYCL_ENABLE_GRAPH":"1","GGML_SYCL_GRAPH_CACHE_SIZE":"64"}); self.assertTrue(e["same_exact_8k_and_full_quality_workload_per_arm"]); self.assertEqual(e["minimum_direct_replays"],120)
    def test_argv(self):
        argv=self.r.Execution(self.r.graph_manifest(self.v)).server_argv(); self.assertEqual(argv[argv.index("-m")+1],self.v["model"]["path"]); self.assertEqual(argv[argv.index("--spec-type")+1],"none"); self.assertNotIn("--spec-draft-model",argv); self.assertEqual(argv[argv.index("-ctk")+1],"f16"); self.assertEqual(argv[argv.index("-ctv")+1],"f16"); self.assertEqual(argv[argv.index("-fit")+1],"off")
    def test_inert(self):
        with tempfile.TemporaryDirectory() as d:
            before=set(Path(d).iterdir()); p=subprocess.run([sys.executable,"-B",str(RUNNER)],cwd=d,text=True,capture_output=True); self.assertEqual(p.returncode,0,p.stderr); self.assertEqual(before,set(Path(d).iterdir())); self.assertTrue(json.loads(p.stdout)["default_is_inert"])
    def test_wrong_ack(self):
        p=subprocess.run([sys.executable,"-B",str(RUNNER),"--execute","--ack","wrong"],text=True,capture_output=True); self.assertNotEqual(p.returncode,0); self.assertIn("exact --ack required",p.stderr)
if __name__=="__main__": unittest.main()
