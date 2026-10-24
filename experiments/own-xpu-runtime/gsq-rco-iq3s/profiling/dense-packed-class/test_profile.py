import importlib.util,json,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('class_b_profile',P/'profile.py');Q=importlib.util.module_from_spec(s);s.loader.exec_module(Q)
B=Q.BUDGET
class Accounting(unittest.TestCase):
 def exercise(self,fail=None,below=0):
  with tempfile.TemporaryDirectory() as root,tempfile.TemporaryDirectory(dir='/dev/shm') as ext:
   out=Path(ext);free=[B.EXTERNAL_FLOOR+B.META+B.REMAINING[0]-below];stages=[];calls=[];holder=[];state={'0':{'x':'hash'},'1':{'x':'hash'}}
   plan={'adapter':{'output':root,'evidence_output':ext,'storage':dict(raw_state_bytes=Q.RAW_BYTES,metadata_forecast_bytes=B.META,root_floor_bytes=B.ROOT_FLOOR,external_floor_bytes=B.EXTERNAL_FLOOR,control_cache_forecast_bytes=B.ROOT_CACHE)},'warmup':{'tokens':[9]},'prompt_tokens':[7,8],'scope':'mock'}
   class Transport:
    def __init__(self,*a,**k):self.out=out;self.children=[types.SimpleNamespace(pid=11),types.SimpleNamespace(pid=12)];self.resets=0;self.dumps=0;holder.append(self)
    def check_alive(self):pass
    def close(self,ok):
     calls.append('finish')
     if fail=='finish':raise RuntimeError('finish refused')
     free[0]-=B.D
   def reset(t,d):
    event='initial_reset' if t.resets==0 else 'second_reset';calls.append(event)
    if fail==event:raise RuntimeError(event+' refused')
    free[0]-=B.T+B.D if t.resets==0 else B.D;t.resets+=1;d.mkdir()
   class Controller:
    def __init__(self,*a):pass
    def run(self,p,cap,eos):calls.append('request'+str(cap));return {'tokens':[2]*cap}
   def hashes(t):
    event=('warmup_target_dump','measured_target_dump','repeat')[t.dumps];calls.append(event)
    if fail==event:raise RuntimeError(event+' refused')
    if t.dumps<2:free[0]-=B.T
    t.dumps+=1;return state
   original=Q.storage_guard
   def guard(p,b=None):
    stages.append(0 if b is None else b.stage);return original(p,b)
   def usage(path):return types.SimpleNamespace(free=B.ROOT_FLOOR+B.ROOT_CACHE if Path(path)==Path(root) else free[0])
   with ExitStack() as stack:
    for obj,name,value in [(Q,'validate_plan',lambda p:None),(Q,'storage_guard',guard),(Q.shutil,'disk_usage',usage),(Q.A,'Transport',Transport),(Q.A,'reset',reset),(Q.A.BASE,'NativeController',Controller),(Q.A,'state_hashes',hashes),(Q.A,'cleanup_failure',lambda *a:[]),(Q.C,'baseline',lambda:{'prompt-00-none':dict(prompt_tokens=[7,8],result={'tokens':[2]*128},state_sha256=state)}),(Q.Q,'closed_map',lambda p:state),(Q.Q,'snapshots',lambda p:{'stamp':'same'}),(Q,'classes',lambda p:{}),(Q.PHASES,'partition',lambda *a:{})]:stack.enter_context(patch.object(obj,name,value))
    try:r=Q.qualification(plan,admit=lambda p:None,check=lambda:None,launch_hook=lambda p:None)
    except (ValueError,RuntimeError) as e:return dict(error=str(e),stages=stages,calls=calls,stage=holder[0].capture_budget.stage if holder and hasattr(holder[0],'capture_budget') else None,free=free[0])
   saved=json.loads((out/'profile-result.json').read_text());return dict(result=r,stages=stages,calls=calls,stage=saved['capture_budget']['stage'],free=free[0],ack=saved['capture_budget']['acknowledged'])
 def test_actual_lifecycle_at_exact_start_threshold(self):
  r=self.exercise();self.assertNotIn('error',r);self.assertEqual(r['stages'],[0,0,1,2,2,3,4,5]);self.assertEqual(r['stage'],5);self.assertEqual(r['ack'],list(B.EVENTS));self.assertEqual(r['free'],B.EXTERNAL_FLOOR+B.META);self.assertEqual(r['calls'],['initial_reset','request8','warmup_target_dump','second_reset','request128','measured_target_dump','repeat','finish'])
 def test_one_byte_below_start_refuses_before_owner(self):
  r=self.exercise(below=1);self.assertIn('forecast/floor',r['error']);self.assertEqual(r['calls'],[]);self.assertIsNone(r['stage'])
 def test_each_stage_exact_boundary_and_one_byte_below(self):
  b=B.Budget()
  for stage,remaining in enumerate(B.REMAINING):
   self.assertEqual(b.stage,stage);threshold=B.EXTERNAL_FLOOR+B.META+remaining;B.check_free(B.ROOT_FLOOR+B.ROOT_CACHE,threshold,b)
   with self.assertRaisesRegex(ValueError,'external'):B.check_free(B.ROOT_FLOOR+B.ROOT_CACHE,threshold-1,b)
   with self.assertRaisesRegex(ValueError,'root'):B.check_free(B.ROOT_FLOOR+B.ROOT_CACHE-1,threshold,b)
   if stage<len(B.EVENTS):b.advance(B.EVENTS[stage])
 def test_failed_ack_or_dump_never_advances(self):
  for event,stage,requests in [('initial_reset',0,0),('warmup_target_dump',1,1),('second_reset',2,1),('measured_target_dump',3,2),('repeat',4,2),('finish',4,2)]:
   with self.subTest(event=event):
    r=self.exercise(fail=event);self.assertIn('refused',r['error']);self.assertEqual(r['stage'],stage);self.assertEqual(sum(x.startswith('request') for x in r['calls']),requests)
 def test_old_fixed_guard_fails_after_warmup(self):
  free=B.EXTERNAL_FLOOR+B.META+B.REMAINING[0]-(2*B.T+B.D)
  self.assertEqual(free,B.EXTERNAL_FLOOR+B.META+B.T+2*B.D)
  with self.assertRaisesRegex(ValueError,'external'):B.check_free(B.ROOT_FLOOR+B.ROOT_CACHE,free,B.Budget())
  b=B.Budget();b.advance('initial_reset');b.advance('warmup_target_dump');B.check_free(B.ROOT_FLOOR+B.ROOT_CACHE,free,b)
 def test_argv_and_initial_forecast_unchanged(self):
  p=dict(output='/tmp/control/ranks',evidence_output='/tmp/evidence',binary='/fixed/binary',context=4096,seconds=1800,max_new=128,mini=False)
  for rank in (0,1):
   a=Q.TOKEN_COMMAND(p,rank,51,52);b=Q.command(p,rank,51,52);a[a.index('--timing')+1]='class';self.assertEqual(a,b)
  self.assertEqual(B.REMAINING[0],694327500);self.assertEqual(B.META,128*1024**2);self.assertEqual(B.EXTERNAL_FLOOR,2*1024**3)
 def test_retained_owner_identity(self):
  error=RuntimeError('original');retained=Q.A.RetainedOwner(error,object(),[])
  class Broken:
   def __init__(self,*a,**k):raise error
  with patch.object(Q,'validate_plan'),patch.object(Q,'storage_guard'),patch.object(Q.A,'Transport',Broken),patch.object(Q.A,'cleanup_failure',side_effect=retained):
   with self.assertRaises(Q.A.RetainedOwner) as c:Q.qualification({'adapter':{}},admit=lambda p:None,check=lambda:None,launch_hook=lambda p:None)
   self.assertIs(c.exception.original,error)
 def test_current_authority_and_expanded_readback_failclosed(self):
  self.assertEqual(Q.BINARY_SHA,'5aef74d5f803b33758711db352ee5e1a393a364e6c33aa9f8a4cdb4478f5fe6a')
  with self.assertRaisesRegex(ValueError,'expanded full readback authority pending'):Q.actual_review()
  with tempfile.TemporaryDirectory() as td:
   r=Path(td)/'review.json';a=Path(td)/'authority.json'
   report=dict(passed=True,native_binary_sha256=Q.BINARY_SHA,all12_target_mtp_exact=True,all24_original_prefixes_exact=True,measured_arms=24,bundles=54,physical_drain=True)
   r.write_text(json.dumps(report));a.write_text(json.dumps(dict(passed=True,path=str(r),sha256=Q.sha(r))))
   with patch.object(Q,'EXPANDED_REVIEW',r),patch.object(Q,'EXPANDED_AUTHORITY',a):
    self.assertEqual(Q.actual_review(),Q.ACTUAL)
    report['physical_drain']=False;r.write_text(json.dumps(report));a.write_text(json.dumps(dict(passed=True,path=str(r),sha256=Q.sha(r))))
    with self.assertRaises(ValueError):Q.actual_review()
 def test_unchanged_budget_and_new_coordinator_globals(self):
  parent=Q.L/'profiling/dense-q6-class/launch-b/budget.py';self.assertEqual((P/'budget.py').read_bytes(),parent.read_bytes())
  s=importlib.util.spec_from_file_location('current_dense_class_once_test',P/'once.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
  self.assertIs(m.O.S,m.S);self.assertIs(m.O.S.A.RetainedOwner,m.S.A.RetainedOwner)
  for mod in (m.O,m.M):self.assertEqual(mod.CONTROL,m.CONTROL);self.assertEqual(mod.EVIDENCE,m.EVIDENCE);self.assertEqual(mod.UNIT,m.UNIT)
  self.assertEqual(m.UNIT,'gsq-dense-packed-class-a.service')
if __name__=='__main__':unittest.main(verbosity=2)
