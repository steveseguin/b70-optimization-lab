import importlib.util,types,unittest
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('rf32_b_tests',P/'once.py');B=importlib.util.module_from_spec(s);s.loader.exec_module(B)
class Tests(unittest.TestCase):
 def test_initial_exact_and_below(self):
  calls=[]
  with patch.object(B.PARENT_TRANSPORT,'__init__',lambda self,*a,**kw:calls.append('owner-construction')):
   with patch.object(B.shutil,'disk_usage',return_value=types.SimpleNamespace(free=B.ROOT_INITIAL_REQUIRED-1)):
    with self.assertRaisesRegex(RuntimeError,'headroom'):B.InitialMarginTransport()
   self.assertEqual(calls,[])
   with patch.object(B.shutil,'disk_usage',return_value=types.SimpleNamespace(free=B.ROOT_INITIAL_REQUIRED)) as d:B.InitialMarginTransport();self.assertEqual(d.call_count,1)
  self.assertEqual(calls,['owner-construction'])
 def test_ongoing_stage0_unchanged(self):
  budget=B.S.BUDGET.Budget();old=B.S.BUDGET.ROOT_FLOOR+B.S.BUDGET.ROOT_CACHE
  self.assertEqual(B.ROOT_INITIAL_REQUIRED-old,128<<20)
  B.S.BUDGET.check_free(old,B.S.BUDGET.EXTERNAL_FLOOR+B.S.BUDGET.META+B.S.BUDGET.REMAINING[0],budget)
  for event in B.S.BUDGET.EVENTS:
   budget.advance(event);B.S.BUDGET.check_free(old,B.S.BUDGET.EXTERNAL_FLOOR+B.S.BUDGET.META+B.S.BUDGET.REMAINING[budget.stage],budget)
 def test_same_modules_and_fresh_identity(self):
  self.assertIs(B.O.S,B.S);self.assertIs(B.S.A.Transport,B.InitialMarginTransport)
  self.assertEqual(B.BASE.CONTROL,B.O.CONTROL);self.assertEqual(B.O.CONTROL,B.M.CONTROL)
  self.assertEqual(B.BASE.EVIDENCE,B.M.EVIDENCE);self.assertEqual(B.BASE.UNIT,'gsq-recurrent-f32-b.service')
  self.assertEqual(B.M.CONTROL.name,'gsq-recurrent-f32-b.control')
 def test_actual_arg_and_reserves(self):
  p=dict(output='/control',evidence_output='/evidence',binary='/pending',context=4096,seconds=1800,max_new=32,mini=False)
  for rank in (0,1):
   cmd=B.S.A.command(p,rank,'9','10');self.assertEqual(cmd.count('--recurrent-f32'),1);self.assertEqual(cmd[cmd.index('--max-new')+1],'32')
  self.assertEqual(B.S.BUDGET.META,128<<20);self.assertEqual(B.S.BUDGET.EXTERNAL_FLOOR,2<<30)
if __name__=='__main__':unittest.main()
