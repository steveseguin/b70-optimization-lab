import copy,importlib.util,json,unittest
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('coverage_archive_scope',P/'closed_coverage_bundles.py');A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
class Scope(unittest.TestCase):
 def test_exact_actual_metadata_plan(self):
  p=A.plan();self.assertEqual((p['files'],p['capture_groups'],p['bytes']),(14,7,1552202176));self.assertFalse(p['operations_performed']);self.assertEqual(p['payload_bytes_read'],0)
  self.assertEqual(len(set(A.NAMES)),14);self.assertLess(125561972+8192+1024**2,A.CAP)
  for i,n in enumerate(A.NAMES):self.assertEqual(n,A.selected(i));self.assertEqual(tuple(n.split('/')),A.C.relative(n))
 def test_bad_paths_and_batches(self):
  for x in ('../state.bundle','/rank0/state.bundle','rank0//state-2147483647/state.bundle','rank0/./state-2147483647/state.bundle','prompt-00-none/rank0/state-2147483647/state.bundle','rank0/state-2147483647/state.json'):
   with self.assertRaises(Exception):A.C.relative(x)
  for x in (-1,14,True,'0'):
   with self.assertRaises(Exception):A.selected(x)
 def test_unbound_refuses(self):
  with patch.object(A,'BINDING_SHA',None),self.assertRaisesRegex(Exception,'not yet bound'):A.plan()
 def test_actual_closure_and_negative_mutations(self):
  b=json.loads(A.BINDING.read_text());r=json.loads((A.AUDIT/'review.json').read_text());t=json.loads((A.CONTROL/'terminal.json').read_text());A.validate_closure(b,r,t)
  for key,value in [('passed',False),('bundles',12),('requests',5),('all_target_mtp_exact',False)]:
   bad=copy.deepcopy(r);bad[key]=value
   with self.assertRaises(Exception):A.validate_closure(b,bad,t)
  bad=copy.deepcopy(t);bad['observed_target_contact']=[True,False]
  with self.assertRaisesRegex(Exception,'positive terminal'):A.validate_closure(b,r,bad)
if __name__=='__main__':unittest.main(verbosity=2)
