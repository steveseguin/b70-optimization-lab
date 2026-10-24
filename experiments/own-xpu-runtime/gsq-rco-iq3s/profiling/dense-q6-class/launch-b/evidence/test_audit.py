import copy,importlib.util,unittest
from pathlib import Path
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('closed_class_b_audit',P/'device-b/audit.py');A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
class Audit(unittest.TestCase):
 def fixture(self):
  full={'capture_budget':dict(stage=5,acknowledged=['initial_reset','warmup_target_dump','second_reset','measured_target_dump','finish'],remaining_payload_bytes=0,metadata_reserve_bytes=134217728,external_floor_bytes=2147483648)}
  plan={'adapter':{'storage':dict(raw_state_bytes=694327500,evidence_forecast_bytes=828545228,metadata_forecast_bytes=134217728,external_floor_bytes=2147483648,root_floor_bytes=27000000000,control_cache_forecast_bytes=134217728)}}
  return full,plan
 def test_closed_budget_and_all_reserves(self):
  full,plan=self.fixture();self.assertEqual(A.closed_budget(full,plan),full['capture_budget'])
  for key in plan['adapter']['storage']:
   wrong=copy.deepcopy(plan);wrong['adapter']['storage'][key]-=1
   with self.subTest(key=key),self.assertRaises(ValueError):A.closed_budget(full,wrong)
 def test_failed_or_missing_ack_chain_refuses(self):
  for kind in ('stage','remaining','missing','reordered'):
   full,plan=self.fixture();b=full['capture_budget']
   if kind=='stage':b['stage']=4
   elif kind=='remaining':b['remaining_payload_bytes']=9699332
   elif kind=='missing':b['acknowledged'].pop()
   else:b['acknowledged'][1:3]=reversed(b['acknowledged'][1:3])
   with self.subTest(kind=kind),self.assertRaises(ValueError):A.closed_budget(full,plan)
 def test_actual_plan_new_identity(self):
  p=P/'device-b/plan.json';plan=A.read(p);self.assertEqual(A.sha(p),A.PLAN_SHA);self.assertEqual(plan['adapter']['binary_sha256'],A.BINARY);self.assertEqual(plan['unit'],'gsq-dense-q6-class-b.service');self.assertEqual(A.L.name,'gsq-rco-iq3s')
if __name__=='__main__':unittest.main(verbosity=2)
