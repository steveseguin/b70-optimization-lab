import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('launch_b_budget_test',P/'once.py');N=importlib.util.module_from_spec(s);s.loader.exec_module(N);B=N.B;S=N.S;A=N.A;C=S.C
s=importlib.util.spec_from_file_location('base_suite_fakes',N.X.L/'baseline/test_suite.py');T=importlib.util.module_from_spec(s);s.loader.exec_module(T)
class Lifecycle(unittest.TestCase):
 def sequence(self):
  yield 'reset'
  yield 'reset'
  for _ in range(24):yield 'reset';yield 'dump'
  yield 'dump';yield 'finish'
 def test_minimal_payload_threshold_and_one_byte_below_every_stage(self):
  b=B.Budget();free=B.EXTERNAL_FLOOR+B.META+b.remaining;root=B.ROOT_FLOOR+B.ROOT_CACHE
  B.check_free(root,free,b)
  with self.assertRaises(ValueError):B.check_free(root,free-1,b)
  for event in self.sequence():
   before=b.remaining;getattr(b,event)();free-=before-b.remaining;self.assertEqual(free,B.EXTERNAL_FLOOR+B.META+b.remaining);B.check_free(root,free,b)
   with self.assertRaises(ValueError):B.check_free(root,free-1,b)
  self.assertTrue(b.finished);self.assertEqual(b.remaining,0);self.assertEqual(len(b.events),52);self.assertEqual((b.resets,b.dumps,b.repeats),(26,24,1))
  with self.assertRaises(ValueError):B.check_free(root-1,free,b)
 def refs(self):
  return {f'prompt-{i:02d}-{mode}':dict(mode=mode,prompt_tokens=p['tokens'],result={'tokens':[2]*128},state_sha256={'0':{'state':'exact'},'1':{'state':'exact'}}) for i,p in enumerate(S.manifest()['prompts']) for mode in p['order']}
 def test_actual_inherited26_request_loop_with_acknowledged_writes(self):
  with tempfile.TemporaryDirectory() as tmp:
   t,reset,controller,dump=T.SuiteTests().fixture(tmp);plan=dict(lifetime_seconds=7200,manifest_sha256=S.sha(S.MANIFEST));free=[B.EXTERNAL_FLOOR+B.META+27*B.PER];guards=[]
   def physical_reset(t,dest):
    reset(t,dest);free[0]-=B.PER if t.capture_budget.resets<3 else B.D
   def physical_dump(t):
    out=dump(t)
    if not t.capture_budget.target_dumped:free[0]-=B.T
    return out
   def physical_close(t,normal):
    self.assertTrue(normal);free[0]-=B.D
   def space(p,b,started=False):guards.append(b.remaining);return B.check_free(B.ROOT_FLOOR+B.ROOT_CACHE,free[0],b)
   with patch.object(N,'RESET',physical_reset),patch.object(N,'DUMP',physical_dump),patch.object(N,'CLOSE',physical_close),patch.object(N,'check_space',side_effect=space),patch.object(A.BASE,'NativeController',controller),patch.object(C,'bind_references'),patch.object(C,'REFERENCES',self.refs()),patch.object(C,'capture_stamp',return_value={}),patch.object(C,'verify_capture_stamps'):
    out=N.run_attached(t,plan);self.assertEqual(t.capture_budget.remaining,B.D);N.close(t,True)
   self.assertTrue(out['passed']);self.assertEqual((len(t.calls),len(t.resets)),(26,26));self.assertEqual(guards[:4],[27*B.PER,26*B.PER,25*B.PER,24*B.PER-B.T]);self.assertEqual(free[0],B.EXTERNAL_FLOOR+B.META);self.assertEqual(out['capture_budget']['remaining_payload_bytes'],0);self.assertTrue(out['capture_budget']['finished'])
 def test_failed_reset_and_dump_do_not_credit(self):
  class F:pass
  t=F();t.capture_budget=B.Budget();before=t.capture_budget.report()
  with patch.object(N,'RESET',side_effect=RuntimeError('reset failed')),self.assertRaises(RuntimeError):N.reset(t,'x')
  self.assertEqual(t.capture_budget.report(),before)
  for _ in range(3):t.capture_budget.reset()
  before=t.capture_budget.report()
  with patch.object(N,'DUMP',side_effect=RuntimeError('dump failed')),self.assertRaises(RuntimeError):N.state_hashes(t)
  self.assertEqual(t.capture_budget.report(),before)
 def test_final_repeat_and_failed_finish_do_not_double_credit(self):
  class F:pass
  t=F();t.capture_budget=B.Budget()
  for e in list(self.sequence())[:-1]:getattr(t.capture_budget,e)()
  self.assertEqual(t.capture_budget.remaining,B.D);before=t.capture_budget.report()
  with patch.object(N,'CLOSE',side_effect=RuntimeError('close failed')),self.assertRaises(RuntimeError):N.close(t,True)
  self.assertEqual(t.capture_budget.report(),before)
  with patch.object(N,'CLOSE',return_value=None):N.close(t,False)
  self.assertEqual(t.capture_budget.report(),before)
  with self.assertRaises(ValueError):t.capture_budget.dump()
 def test_illegal_order_and_counts_refused(self):
  b=B.Budget()
  with self.assertRaises(ValueError):b.dump()
  for _ in range(3):b.reset()
  with self.assertRaises(ValueError):b.reset()
  b.dump()
  with self.assertRaises(ValueError):b.dump()
  with self.assertRaises(ValueError):b.finish()
  with patch.object(N,'CURRENT',b),self.assertRaisesRegex(ValueError,'count agrees'):N.storage_guard({},completed=0)
 def test_floors_and_full27_capture_authority_retained(self):
  class Stat: 
   def __init__(self,dev):self.st_dev=dev
  class Free:
   def __init__(self,n):self.free=n
  plan=dict(adapter=dict(output='/root/control',evidence_output='/external/evidence'),storage=dict(retained_state_dumps=27,per_request_state_bytes=B.PER,evidence_forecast_bytes=27*B.PER+B.META,root_floor_bytes=B.ROOT_FLOOR,root_cache_forecast_bytes=B.ROOT_CACHE,external_floor_bytes=B.EXTERNAL_FLOOR))
  def st(p):return Stat(1 if str(p).startswith('/root') else 2)
  def free(p):return Free(B.ROOT_FLOOR+B.ROOT_CACHE if str(p).startswith('/root') else B.EXTERNAL_FLOOR+B.META+27*B.PER)
  with patch.object(Path,'stat',st),patch.object(N.shutil,'disk_usage',side_effect=free):
   N.check_space(plan,B.Budget(),True)
   plan['storage']['retained_state_dumps']=26
   with self.assertRaises(ValueError):N.check_space(plan,B.Budget(),True)
 def test_private_globals_and_retained_owner_identity(self):
  self.assertIs(N.O.S,N.S);self.assertIs(N.O.S.A.RetainedOwner,N.A.RetainedOwner)
  for m in (N.X,N.O,N.M):self.assertEqual(m.CONTROL,N.CONTROL);self.assertEqual(m.EVIDENCE,N.EVIDENCE);self.assertEqual(m.UNIT,N.UNIT)
  self.assertEqual(N.UNIT,'gsq-dense-packed-block-engine-b.service')
if __name__=='__main__':unittest.main(verbosity=2)
