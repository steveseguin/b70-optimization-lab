import importlib.util,pathlib,types,unittest
from unittest.mock import patch
P=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('f32_test_suite',P/'suite.py');S=importlib.util.module_from_spec(spec);spec.loader.exec_module(S)
class Tests(unittest.TestCase):
 def test_pending_authority(self):
  with self.assertRaisesRegex(ValueError,'pending'):S.authority()
 def test_budget(self):
  b=S.BUDGET.Budget();self.assertEqual(S.RAW,960190668)
  for i,e in enumerate(S.BUDGET.EVENTS):
   minimum=S.BUDGET.EXTERNAL_FLOOR+S.BUDGET.META+S.BUDGET.REMAINING[i]
   S.BUDGET.check_free(S.BUDGET.ROOT_FLOOR+S.BUDGET.ROOT_CACHE,minimum,b)
   with self.assertRaises(ValueError):S.BUDGET.check_free(S.BUDGET.ROOT_FLOOR+S.BUDGET.ROOT_CACHE,minimum-1,b)
   b.advance(e)
  self.assertEqual(b.report()['remaining_payload_bytes'],0)
 def fake(self,fail=False,mismatch=False):
  t=types.SimpleNamespace(out=pathlib.Path('/fake'),children=[types.SimpleNamespace(pid=1),types.SimpleNamespace(pid=2)],check_alive=lambda:None)
  calls=[];n=[0]
  def dump(t):
   n[0]+=1
   if fail:raise RuntimeError('dump failure')
   return {'0':{'f32-state':'different' if mismatch and n[0]==2 else 'new-f32'},'1':{'f32-state':'new-f32'}}
  state={'0':{'f32-state':'new-f32'},'1':{'f32-state':'new-f32'}}
  class Controller:
   def __init__(self,*a):pass
   def run(self,p,cap,eos):calls.append((p,cap));return {'tokens':[1,2]}
  stack=[patch.object(S.A,'reset',lambda t,p:None),patch.object(S.A,'state_hashes',dump),patch.object(S.A,'save',lambda *a:None),patch.object(S.A.BASE,'NativeController',Controller),patch.object(S.Q,'closed_map',lambda p:state),patch.object(S.Q,'snapshots',lambda p:{'stable':1}),patch.object(S,'storage_guard',lambda p,b=None:None)]
  import contextlib
  with contextlib.ExitStack() as cm:
   for x in stack:cm.enter_context(x)
   result=S.run_attached(t,{'prompt_tokens':[7]*87,'reference_tokens':[3,4]})
  return result,t,calls
 def test_pair_and_diagnostic(self):
  r,t,c=self.fake();self.assertTrue(r['corrected_target_mtp_exact']);self.assertFalse(r['reference_equal']);self.assertEqual([x[1] for x in c],[32,32]);self.assertEqual(t.capture_budget.stage,4)
 def test_dump_failure(self):
  with self.assertRaisesRegex(RuntimeError,'dump failure'):self.fake(fail=True)
 def test_pair_mismatch(self):
  with self.assertRaisesRegex(ValueError,'full state differ'):self.fake(mismatch=True)
if __name__=='__main__':unittest.main()
