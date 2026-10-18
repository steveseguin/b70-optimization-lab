"""CPU-only worker flow and drain race checks; all transport work is synthetic."""
import json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from bootstrap import P,install
install()
import worker
from common import D,P56
sys.path.insert(0,str(P56))
import pipeline,suite
from conditions import Teardown as OldTeardown
from teardown import Teardown
class Tests(unittest.TestCase):
 def test_wrapper_only_changes_evidence_namespace(self):
  original=(P.parent/'screen/v4-lanes/screen.py').read_text()
  expected=original.replace("args.output.is_relative_to(HERE / 'evidence')","args.output.is_relative_to(Path(__file__).resolve().parent / 'evidence')")
  self.assertEqual((P/'screen128.py').read_text(),expected)
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
 def test_clock_crossing_fixed(self):self.assertEqual(self.race(Teardown),[0.0])
 def test_original_race_negative_control(self):
  with self.assertRaisesRegex(ValueError,'negative'):self.race(OldTeardown)
 def test_real_worker_twelve_exact_64_requests_one_load(self):
  class FakeTransport:
   loads=0
   def __init__(self,args,ranks,*a,**k):self.args=args;self.out=ranks;self.closed=False;self.children=[];FakeTransport.loads+=1
  entries=D.oracle_inputs()['prompts'];calls=[];resets=[]
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'run'
   def request(t,args,prompt,count):
    i=len(calls);calls.append(count);expected=D.CHECK.token_record(D.ORACLE/'results'/entries[i]['prompt_id'])[:count]
    row=dict(passed=True,tokens=expected,decode_intervals=63,decode_wall_ms=1050)
    (t.out/'native-result.json').write_text(json.dumps(row));return row
   def reset(t,dest):dest.mkdir(parents=True);resets.append(dest.name)
   def poll(**k):(out/'device-isolation.json').write_text(json.dumps(dict(passed=True,synthetic=True)))
   monitor=SimpleNamespace(poll=poll,register=lambda pid:None)
   # This tests loop/argument/oracle behavior only. Real launch assembly has a
   # separate intercepted-exec gate; no device or operational admission here.
   import placement
   identity=dict(lineage=str(P),selection_sha256='fixture',binary='never-executed',dispatch=str(P/'dispatch-speed6.json'),timing='attribution',lane='B')
   placement_value=dict(draft_rank=1,target_split=0)
   with patch.object(placement,'verify_identity',return_value=(placement_value,SimpleNamespace())),patch.object(pipeline,'Transport',FakeTransport),patch.object(suite,'reset',side_effect=reset),patch.object(suite,'run_request',side_effect=request),patch.object(worker,'DeviceMonitor',return_value=monitor),patch.object(worker,'masked_environment',return_value={}),patch.object(worker,'drain') as drain,patch.object(worker.SUPPORT,'storage'):
    self.assertEqual(worker.run(identity,out,3600),0)
   proof=json.loads((out/'report-inputs.json').read_text());self.assertEqual(FakeTransport.loads,1);self.assertEqual(calls,[64]*12);self.assertEqual(len(resets),13);self.assertEqual([r['attribution_request'] for r in proof['requests']],list(range(1,13)));drain.assert_called_once()
   self.assertEqual(proof['incident64']['mode'],'first-suite-request')
   for r in proof['requests']:self.assertTrue((out/r['prompt_id']/'native-result.json').exists())
if __name__=='__main__':unittest.main()
