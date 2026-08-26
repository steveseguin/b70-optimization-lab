#!/usr/bin/env python3
"""Focused inert tests for the Q4_K_XL graph curve cache64 R3."""
import importlib.util,json,subprocess,sys,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent;RUNNER_PATH=HERE/"run-20260826-qwen38-q4kxl-f16kv-tp1-sycl-graph-cache64-depth-quality-r3.py"
def load_runner():
    spec=importlib.util.spec_from_file_location("qwen38_q4kxl_graph_curve_r3_tested",RUNNER_PATH);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module
class PacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.runner=load_runner();cls.value=cls.runner.load_manifest()
    def test_only_capacity_and_identity_change(self):
        self.assertEqual(self.value["execution_contract"]["graph_environment"]["GGML_SYCL_GRAPH_CACHE_SIZE"],"64");self.assertEqual(self.value["selectors"]["graph_mode"],"SYCL graph cache64");self.assertEqual(self.value["server_contract"]["graph"],"SYCL cache64");self.assertEqual(self.value["graph_acceptance"]["cache_limit"],64);self.assertEqual(self.value["graph_acceptance"]["minimum_direct_replays"],896);self.assertEqual(self.value["model"],self.runner.R2_VALUE["model"]);self.assertEqual(self.value["runtime"],self.runner.R2_VALUE["runtime"])
        self.runner.verify_base(self.runner.load_overlay())
    def test_cache64_parser_and_no_escalation(self):
        text="[SYCL-GRAPH] summary device=0 requested=1182 compatibility_rejected=0 device_unsupported=0 cache_entries=64 cache_limit=64 cache_hit=1000 cache_miss=182 cache_full=118 direct_replay=1000 recorded=64 created=64 updated=0 recreated=0 replayed=1064";self.assertEqual(self.runner.parse_graph_evidence(text)["direct_replay"],1000);self.assertTrue(self.runner.load_overlay()["mechanism_delta"]["no_further_capacity_escalation"])
    def test_inert_default(self):
        with tempfile.TemporaryDirectory() as directory:
            before=set(Path(directory).iterdir());result=subprocess.run([sys.executable,str(RUNNER_PATH)],cwd=directory,text=True,capture_output=True);self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(before,set(Path(directory).iterdir()));plan=json.loads(result.stdout);self.assertEqual(plan["candidate_cache_limit"],64);self.assertFalse(plan["further_capacity_escalation"])
if __name__=="__main__":unittest.main()
