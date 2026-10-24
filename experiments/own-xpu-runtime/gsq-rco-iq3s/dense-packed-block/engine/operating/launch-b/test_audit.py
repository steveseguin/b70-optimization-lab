"""No live result reads: fixed successful budget and corruption refusals only."""
import copy,importlib.util,unittest
from pathlib import Path
P=Path(__file__).resolve().parent
def load(name,file):
 s=importlib.util.spec_from_file_location(name,P/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
A=load('storage_b_audit','audit.py');B=load('storage_b_budget','budget.py')
class Tests(unittest.TestCase):
 def complete(self):
  b=B.Budget()
  for i in range(26):
   b.reset()
   if i>=2:b.dump()
  b.dump();b.finish();return b.report()
 def test_independent_sequence_agrees_with_successful_controller(self):
  got=self.complete();self.assertEqual(A.validate_capture_budget(got),got);self.assertEqual(len(got['events']),52)
 def test_no_unacknowledged_duplicate_or_reserve_waiver(self):
  original=self.complete()
  for field,value in [('finished',False),('target_dumps',23),('remaining_payload_bytes',1),('metadata_reserve_bytes',0),('external_floor_bytes',0)]:
   bad=copy.deepcopy(original);bad[field]=value
   with self.assertRaisesRegex(ValueError,'capture budget'):A.validate_capture_budget(bad)
  for index in (0,2,3,49,50,51):
   bad=copy.deepcopy(original);bad['events'][index]['credited_bytes']+=1
   with self.assertRaisesRegex(ValueError,'capture budget'):A.validate_capture_budget(bad)
  bad=copy.deepcopy(original);bad['events'].append(bad['events'][-1])
  with self.assertRaisesRegex(ValueError,'capture budget'):A.validate_capture_budget(bad)
 def test_bound_binary_pending_new_plan_and_correct_roots(self):
  self.assertIsNone(A.PLAN_SHA);self.assertEqual(A.BUILD_SHA,'3fe225c3c7076fbf680b3d7e0d1a051e533a34b5ed059da0048b8743323aed95')
  self.assertEqual(A.BINARY,'5aef74d5f803b33758711db352ee5e1a393a364e6c33aa9f8a4cdb4478f5fe6a')
  self.assertEqual(A.CAND.name,'engine');self.assertEqual(A.L.name,'gsq-rco-iq3s');self.assertEqual(A.D.name,'device-b')
  self.assertTrue(str(A.CONTROL).endswith('engine-b.control'));self.assertTrue(str(A.EVIDENCE).endswith('engine-b'))
  with self.assertRaisesRegex(ValueError,'fixed admitted plan'):A.run('0'*64)
if __name__=='__main__':unittest.main(verbosity=2)
