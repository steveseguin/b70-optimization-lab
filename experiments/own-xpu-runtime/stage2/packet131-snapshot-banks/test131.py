"""Real request-loop, drain-race and teardown-on-error regressions; CPU only."""
import importlib.util,json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from bootstrap import P,install
install()
import smoke_worker,grid_worker
from common import D,P56
sys.path.insert(0,str(P56))
import pipeline,suite
from conditions import Teardown as OriginalTeardown
from teardown import Teardown
class Tests(unittest.TestCase):
 def test_two_fresh_wins_and_unchanged_acceptance(self):
  from compare131 import compare,ORDER
  rows=[dict(choice=c,boot_id='synthetic',lane='B',all_13_exact=True,started_utc_ns=i*10,finished_utc_ns=i*10+1,acceptance_counts=[{'hits':80,'guesses':100}],rate=62 if c=='candidate' else 60) for i,c in enumerate(ORDER)]
  self.assertTrue(compare(rows)['candidate_qualified'])
  rows[3]['rate']=59;self.assertFalse(compare(rows)['candidate_qualified'])
  rows[3]['rate']=62;rows[2]['rate']=58;self.assertFalse(compare(rows)['candidate_qualified'])
  rows[2]['rate']=60;rows[1]['acceptance_counts']=[{'hits':81,'guesses':100}]
  with self.assertRaisesRegex(ValueError,'acceptance'):compare(rows)
 def race(self,cls):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);out=root/'out';out.mkdir();clock=iter([59.9,60.1,60.1,60.1,60.1]);sleeps=[]
   def sleep(value):
    if value<0:raise ValueError('negative sleep')
    sleeps.append(value)
   gate=cls(out,root=root,now=lambda:next(clock),sleep=sleep)
   (root/'teardown-state.json').write_text(json.dumps(dict(boot_id=gate.boot,drained=True,completed_monotonic=0)))
   with gate:pass
   return sleeps
 def test_drain_race(self):self.assertEqual(self.race(Teardown),[0.0])
 def test_original_negative(self):
  with self.assertRaisesRegex(ValueError,'negative'):self.race(OriginalTeardown)
 def test_graceful_error_teardown(self):
  for worker in (smoke_worker,grid_worker):
   class Permit:
    def __init__(self,*a,**k):pass
    def __enter__(self):return self
    def __exit__(self,*a):return False
   calls=[]
   def close(success):
    calls.append(('close',success))
    if success:raise ValueError('injected FINISH error')
   transport=SimpleNamespace(close=close,stop=lambda reason:calls.append(('stop',str(reason))),check=lambda:None)
   with patch.object(worker,'Teardown',Permit),self.assertRaisesRegex(ValueError,'injected'):
    worker.drain(transport,Path('/unused'),True)
   self.assertEqual(calls,[('close',True),('stop','injected FINISH error'),('close',False)])
 def test_permit_refusal_stops_own_ranks(self):
  for worker in (smoke_worker,grid_worker):
   calls=[]
   class Permit:
    def __init__(self,*a,**k):self.refused=k['on_refusal']
    def __enter__(self):self.refused('injected permit refusal');raise ValueError('refusal')
    def __exit__(self,*a):return False
   transport=SimpleNamespace(close=lambda ok:calls.append(('close',ok)),stop=lambda reason:calls.append(('stop',str(reason))),check=lambda:None)
   with patch.object(worker,'Teardown',Permit),self.assertRaisesRegex(ValueError,'refusal'):
    worker.drain(transport,Path('/unused'),True)
   self.assertEqual(calls,[('stop','injected permit refusal'),('close',False)])
   self.assertTrue(transport.teardown_refused)
 def test_smoke_and_grid_complete_exact_suite(self):
  for worker,smoke in ((smoke_worker,True),(grid_worker,False)):
   class FakeTransport:
    loads=0
    def __init__(self,args,ranks,*a,**k):self.args=args;self.out=ranks;self.closed=False;self.children=[];FakeTransport.loads+=1
   entries=D.oracle_inputs()['prompts'];calls=[];resets=[]
   requests=[(e,64) for e in entries] if smoke else [(entries[0],64)]+[(e,128) for e in entries]
   with tempfile.TemporaryDirectory() as d:
    out=Path(d)/'run'
    def request(t,args,prompt,count):
     e,n=requests[len(calls)];self.assertEqual(n,count);calls.append(count)
     expected=D.CHECK.token_record(D.ORACLE/'results'/e['prompt_id'])[:count]
     return dict(passed=True,tokens=expected,decode_intervals=count-1,decode_wall_ms=2000,cached_tokens=0)
    def reset(t,dest):dest.mkdir(parents=True);resets.append(dest.name)
    def poll(**k):(out/'device-isolation.json').write_text(json.dumps(dict(passed=True,synthetic=True)))
    monitor=SimpleNamespace(poll=poll,register=lambda pid:None)
    import placement
    identity=dict(lineage=str(P),selection_sha256='fixture',binary='never-executed',dispatch=str(P/'dispatch-speed6.json'),timing='token',lane='B')
    with patch.object(placement,'verify_identity',return_value=(dict(draft_rank=1,target_split=0),SimpleNamespace())),patch.object(pipeline,'Transport',FakeTransport),patch.object(suite,'reset',side_effect=reset),patch.object(suite,'run_request',side_effect=request),patch.object(worker,'DeviceMonitor',return_value=monitor),patch.object(worker,'masked_environment',return_value={}),patch.object(worker,'drain') as drain,patch.object(worker.SUPPORT,'storage'):
     self.assertEqual(worker.run(identity,out,3600),0)
    proof=json.loads((out/'report-inputs.json').read_text());self.assertEqual(FakeTransport.loads,1);self.assertEqual(calls,[n for e,n in requests]);self.assertEqual(len(resets),len(requests)+1);drain.assert_called_once()
    self.assertEqual([r['prompt_id'] for r in proof['requests']],[e['prompt_id'] for e in entries])
    self.assertTrue(all(r['exact_oracle'] for r in proof['requests']))
if __name__=='__main__':unittest.main()
