"""Small source/metadata checks; never open current diagnostic payloads."""
from pathlib import Path
import ast,copy,hashlib,importlib.util,json,unittest
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('dense_packed_class_readback_test',P/'device-a/audit.py');A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
class Tests(unittest.TestCase):
 def test_actual_admitted_identity(self):
  path=Path('/home/steve/own-xpu-runtime-results/gsq-dense-packed-class-a-plan.json')
  self.assertEqual(A.sha(path),A.PLAN_SHA);p=json.loads(path.read_text())
  self.assertEqual(p['adapter']['binary_sha256'],A.BINARY);self.assertEqual(p['adapter']['build_receipt_sha256'],A.BUILD_SHA)
  self.assertEqual(p['suite']['expanded_actual_review_sha256'],A.EXPANDED_SHA);self.assertEqual(p['suite']['candidate_actual_review_sha256'],A.ACTUAL_SHA)
  self.assertEqual(p['requests'],2);self.assertEqual(A.P.name,'dense-packed-class');self.assertEqual(A.L.name,'gsq-rco-iq3s')
 def test_stream_phase_and_budget_functions_unchanged(self):
  def functions(p):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef)}
  old=functions(A.QUALIFIED_PARENT);new=functions(P/'device-a/audit.py')
  for name in ('stream_bundle','derive_phases','closed_budget','stamp','snapshot','unique','digest','number'):self.assertEqual(old[name],new[name],name)
 def test_final_budget_and_early_finish_refusal(self):
  budget=dict(stage=5,acknowledged=['initial_reset','warmup_target_dump','second_reset','measured_target_dump','finish'],remaining_payload_bytes=0,metadata_reserve_bytes=134217728,external_floor_bytes=2147483648)
  plan=dict(adapter=dict(storage=dict(raw_state_bytes=694327500,evidence_forecast_bytes=828545228,metadata_forecast_bytes=134217728,external_floor_bytes=2147483648,root_floor_bytes=27000000000,control_cache_forecast_bytes=134217728)))
  self.assertEqual(A.closed_budget(dict(capture_budget=budget),plan),budget)
  for field,value in [('stage',4),('remaining_payload_bytes',9699332),('acknowledged',budget['acknowledged'][:-1])]:
   bad=copy.deepcopy(budget);bad[field]=value
   with self.assertRaises(ValueError):A.closed_budget(dict(capture_budget=bad),plan)
if __name__=='__main__':unittest.main(verbosity=2)
