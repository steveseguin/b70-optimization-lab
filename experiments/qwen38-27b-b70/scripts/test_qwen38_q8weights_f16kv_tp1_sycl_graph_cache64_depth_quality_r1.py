#!/usr/bin/env python3
"""Focused inert tests for the Q8_0 cache64 graph curve packet."""
import importlib.util,json,subprocess,sys,tempfile,unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent;RUNNER_PATH=HERE/"run-20260826-qwen38-q8weights-f16kv-tp1-sycl-graph-cache64-depth-quality-r1.py"
def load_runner():
    spec=importlib.util.spec_from_file_location("qwen38_q8weights_graph_curve_tested",RUNNER_PATH);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module

class PacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.runner=load_runner();cls.value=cls.runner.load_manifest();cls.merged=cls.runner.merged_manifest(cls.value)
    def test_exact_model_runtime_and_scope(self):
        self.assertEqual(self.value["model"]["quantization"],"Q8_0");self.assertEqual(self.value["model"]["sha256"],"f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8");self.assertEqual(self.value["runtime"],self.runner.ENGINE_VALUE["runtime"])
        self.assertEqual(self.value["selectors"]["active_context_tokens"],[0,2048,4096,8192,16384,24576,32768]);self.assertIsNone(self.value["frozen_interpretation"]["speed_floor"]);self.assertEqual(self.value["frozen_interpretation"]["protected_decode_values"],[71.45427094575045,30.329809361830037,49.05894025767351,71.9001988117144])
    def test_capacity_and_parser(self):
        decision=self.value["capacity_decision"];self.assertEqual(decision["selected_cache_size"],64);self.assertEqual(decision["q8_sentinel_direct_replays"],202);self.assertEqual(decision["q4kxl_same_workload_cache64_direct_replays"],947);self.assertEqual(decision["q5_same_workload_cache64_direct_replays"],947);self.assertTrue(decision["no_further_capacity_escalation"])
        text="[SYCL-GRAPH] summary device=0 requested=1182 compatibility_rejected=0 device_unsupported=0 cache_entries=64 cache_limit=64 cache_hit=947 cache_miss=235 cache_full=171 direct_replay=947 recorded=64 created=64 updated=0 recreated=0 replayed=1011";self.assertEqual(self.runner.parse_graph_evidence(text)["direct_replay"],947)
        with self.assertRaises(self.runner.GateError):self.runner.parse_graph_evidence(text.replace("direct_replay=947","direct_replay=895"))
    def test_report_preflight(self):
        self.assertEqual(self.merged["zero_context_semantics"]["definition"],"zero prior active context before submitting the minimal explicit prompt token")
        graph=self.runner.parse_graph_evidence("[SYCL-GRAPH] summary device=0 requested=1182 compatibility_rejected=0 device_unsupported=0 cache_entries=64 cache_limit=64 cache_hit=947 cache_miss=235 cache_full=171 direct_replay=947 recorded=64 created=64 updated=0 recreated=0 replayed=1011");report=self.runner.compose_terminal_report({"checks":{"base":True,"graph":True},"cells":[{}]*7},graph,self.value)
        self.assertEqual(report["status"],"completed-valid-q8weights-f16kv-graph-cache64-depth-quality");self.assertEqual(report["authority"]["graph_q8weights_f16_serving_curve_cells"],7);self.assertFalse(report["authority"]["protected_or_headline_replacement"])
    def test_passed_sentinel_is_exactly_bound(self):
        deps=self.runner.load_overlay()["dependencies"];terminal=self.runner.load_json(self.runner.resolve(deps["sentinel_terminal"]["path"]));graph=self.runner.load_json(self.runner.resolve(deps["sentinel_graph_evidence"]["path"]))
        self.assertEqual(terminal["status"],"completed-valid-q8weights-f16kv-graph-cache64-8k-sentinel");self.assertTrue(terminal["authority"]["seven_depth_full_curve_preregistration"]);self.assertEqual(terminal["authority"]["site_cells"],0);self.assertEqual(graph,terminal["graph_evidence"]);self.assertEqual(graph["direct_replay"],202)
    def test_inert_default_and_wrong_ack(self):
        with tempfile.TemporaryDirectory() as directory:
            before=set(Path(directory).iterdir());result=subprocess.run([sys.executable,str(RUNNER_PATH)],cwd=directory,text=True,capture_output=True);self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(before,set(Path(directory).iterdir()));plan=json.loads(result.stdout);self.assertEqual(plan["gpu_actions"],0);self.assertEqual(plan["candidate_cache_limit"],64);self.assertTrue(plan["report_composition_preflight"]);self.assertFalse(plan["further_capacity_escalation"])
        result=subprocess.run([sys.executable,str(RUNNER_PATH),"--execute","--ack","wrong"],text=True,capture_output=True);self.assertNotEqual(result.returncode,0);self.assertIn("exact --ack required",result.stderr)

if __name__=="__main__":unittest.main()
