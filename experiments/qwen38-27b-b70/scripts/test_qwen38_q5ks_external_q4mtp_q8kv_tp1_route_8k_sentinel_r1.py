#!/usr/bin/env python3
from __future__ import annotations
import importlib.util,json,subprocess,sys,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
RUNNER_PATH=HERE/"run-20260825-qwen38-q5ks-external-q4mtp-q8kv-tp1-route-8k-sentinel-r1.py"
def load(path,name):
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
R=load(RUNNER_PATH,"qwen38_q5ks_external_mtp_route_test_runner")
class Tests(unittest.TestCase):
 def setUp(self):self.v=R.load_manifest();self.m=R.merged_manifest(self.v);self.m["draft_model"]=self.v["draft_model"]
 def test_exact_artifact_and_runtime_identities(self):
  self.assertEqual(self.v["model"]["sha256"],"d8d62ffcf84d42658dd6ccf9782b4d0404700af78b26d750507510c7597b5bfe");self.assertEqual(self.v["draft_model"]["sha256"],"50d9ce5a6da381bbcfb31061cf73df94a90e6faf8efeddee379a9cb8f1501c6e");self.assertEqual(self.v["runtime"]["source_commit"],"9fee29e9435f865ec0b811a783a6471a136d9317")
 def test_route_argv_is_external_q8kv_graph_off(self):
  ex=R.Execution(self.m)
  for mtp in R.ROUTES:
   argv=ex.server_argv_for_mtp(mtp);self.assertEqual(argv[argv.index("-m")+1],self.v["model"]["path"]);self.assertEqual(argv[argv.index("-ctk")+1],"q8_0");self.assertEqual(argv[argv.index("-ctv")+1],"q8_0");self.assertEqual(argv[argv.index("-fit")+1],"off")
   if mtp:self.assertEqual(argv[argv.index("--spec-type")+1],"draft-mtp");self.assertEqual(argv[argv.index("--spec-draft-model")+1],self.v["draft_model"]["path"]);self.assertEqual(argv[argv.index("--spec-draft-n-max")+1],str(mtp));self.assertEqual(argv[argv.index("--spec-draft-type-k")+1],"q8_0");self.assertEqual(argv[argv.index("--spec-draft-type-v")+1],"q8_0");self.assertEqual(argv[argv.index("--spec-draft-device")+1],"SYCL0")
   else:self.assertEqual(argv[argv.index("--spec-type")+1],"none");self.assertNotIn("--spec-draft-model",argv)
 def test_inert_plan(self):
  result=subprocess.run([sys.executable,"-B",str(RUNNER_PATH),"--check"],check=True,text=True,capture_output=True);plan=json.loads(result.stdout);self.assertEqual((plan["gpu_actions"],plan["network_requests"],plan["output_writes"]),(0,0,0));self.assertEqual(plan["arms"],["control-mtp0","candidate-mtp1","candidate-mtp2","candidate-mtp3","candidate-mtp4"]);self.assertEqual(plan["quality_batteries_max"],4);self.assertEqual(plan["site_cells_authorized"],0)
 def test_frozen_authority(self):
  f=self.v["frozen_interpretation"];self.assertIsNone(f["speed_floor"]);self.assertFalse(f["curve_expansion_authorized"]);self.assertEqual(f["site_cells_authorized"],0)
 def test_quality_helper_has_seven_exact_plus_repeat_and_long(self):
  helper=load(R.REPO/self.v["quality"]["helper"],"qwen38_quality_helper_for_route_test")
  self.assertEqual(len(helper.make_exact_cases()),7);self.assertEqual(self.v["quality"]["run_for_each_exact_parity_candidate"],True)
if __name__=="__main__":unittest.main()
