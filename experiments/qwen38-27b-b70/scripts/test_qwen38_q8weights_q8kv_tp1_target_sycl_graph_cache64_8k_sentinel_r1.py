#!/usr/bin/env python3
"""Focused inert tests for the Q8/Q8-KV cache64 graph sentinel."""
import importlib.util,json,subprocess,sys,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent; RUNNER=HERE/"run-20260826-qwen38-q8weights-q8kv-tp1-target-sycl-graph-cache64-8k-sentinel-r1.py"
def load():
    spec=importlib.util.spec_from_file_location("q8_q8kv_graph_sentinel_tested",RUNNER); m=importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; spec.loader.exec_module(m); return m
class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.r=load(); cls.v=cls.r.load_manifest()
    def test_authority(self):
        f=self.v["frozen_interpretation"]; self.assertEqual(f["site_cells_authorized"],0); self.assertTrue(f["sentinel_pass_authorizes_separate_q8kv_seven_depth_full_curve_preregistration"]); self.assertFalse(f["full_graph_curve_authorized"]); self.assertIsNone(f["speed_floor"])
    def test_structural_evidence_does_not_transfer_kv_authority(self):
        c=self.v["capacity_decision"]; self.assertEqual(c["selected_cache_size"],64); self.assertEqual(c["source_supported_maximum"],64); self.assertTrue(c["no_further_capacity_escalation"]); self.assertEqual(c["structural_predecessor"]["kv_dtype"],"f16"); self.assertEqual(self.v["frozen_interpretation"]["f16_kv_cells_authorized"],0)
    def test_exact_arm_delta_and_dual_quality(self):
        e=self.v["execution_contract"]; self.assertEqual(e["control_environment_delta"],{"GGML_SYCL_ENABLE_GRAPH":"0","GGML_SYCL_GRAPH_CACHE_SIZE":"0"}); self.assertEqual(e["candidate_environment_delta"],{"GGML_SYCL_ENABLE_GRAPH":"1","GGML_SYCL_GRAPH_CACHE_SIZE":"64"}); self.assertTrue(e["same_exact_8k_and_full_quality_workload_per_arm"]); self.assertTrue(e["require_exact_128_token_id_text_usage_and_prompt_parity"]); self.assertEqual(e["minimum_direct_replays"],120)
    def test_argv(self):
        argv=self.r.Execution(self.r.graph_manifest(self.v)).server_argv(); self.assertEqual(argv[argv.index("-m")+1],self.v["model"]["path"]); self.assertEqual(argv[argv.index("--spec-type")+1],"none"); self.assertNotIn("--spec-draft-model",argv); self.assertEqual(argv[argv.index("-ctk")+1],"q8_0"); self.assertEqual(argv[argv.index("-ctv")+1],"q8_0"); self.assertEqual(argv[argv.index("-fit")+1],"off")
    def test_graph_accounting(self):
        row="[SYCL-GRAPH] summary device=0 requested=306 compatibility_rejected=0 device_unsupported=0 cache_entries=64 cache_limit=64 cache_hit=200 cache_miss=106 cache_full=42 direct_replay=200 recorded=64 created=64 updated=0 recreated=0 replayed=264"; out=self.r.parse_graph_evidence(row,self.v); self.assertEqual(out["direct_replay"],200); self.assertEqual(out["summary_count"],1)
    def test_inert(self):
        with tempfile.TemporaryDirectory() as d:
            before=set(Path(d).iterdir()); p=subprocess.run([sys.executable,"-B",str(RUNNER)],cwd=d,text=True,capture_output=True); self.assertEqual(p.returncode,0,p.stderr); self.assertEqual(before,set(Path(d).iterdir())); plan=json.loads(p.stdout); self.assertTrue(plan["default_is_inert"]); self.assertEqual(plan["gpu_actions"],0); self.assertEqual(plan["network_requests"],0); self.assertEqual(plan["output_writes"],0)
    def test_wrong_ack(self):
        p=subprocess.run([sys.executable,"-B",str(RUNNER),"--execute","--ack","wrong"],text=True,capture_output=True); self.assertNotEqual(p.returncode,0); self.assertIn("exact --ack required",p.stderr)
if __name__=="__main__": unittest.main()
