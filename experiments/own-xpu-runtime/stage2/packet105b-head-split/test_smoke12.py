"""Exercise the actual twelve-request worker loop with CPU protocol stand-ins."""
import json,tempfile,types,unittest,sys
from pathlib import Path
from unittest.mock import patch
import smoke_worker as worker
from build_engine import P

class SmokeLoop(unittest.TestCase):
 def exercise(self,corrupt=False):
  manifest=worker.D.oracle_inputs();entries=manifest['prompts'];ids=[r['prompt_id'] for r in entries]
  self.assertEqual(len(ids),12)
  oracle={i:worker.D.CHECK.token_record(worker.D.ORACLE/'results'/i) for i in ids}
  calls=[];resets=[];drains=[]
  class Transport:
   def __init__(self,*a,**kw):self.children=[];self.closed=False;self.stop_write=10
  parser=types.SimpleNamespace(parse_args=lambda argv:types.SimpleNamespace())
  pipeline=types.SimpleNamespace(parser=lambda:parser,Transport=Transport)
  def request(transport,args,prompt,count):
   pid=ids[prompt[0]];calls.append((pid,count));tokens=list(oracle[pid][:count])
   if corrupt and pid=='architecture-tradeoff':tokens[30]=440
   return dict(passed=True,tokens=tokens,cached_tokens=0)
  def reset(transport,dest):dest.mkdir();resets.append(dest.name)
  def snapshots(entries,out,checker):return {r['prompt_id']:(out,[i]) for i,r in enumerate(entries)}
  suite=types.SimpleNamespace(checker_module=lambda p:None,admit_inputs=snapshots,reset=reset,run_request=request)
  memory=types.SimpleNamespace()
  import placement
  with tempfile.TemporaryDirectory(prefix='smoke-loop-',dir=P/'build/tmp') as tmp:
   root=Path(tmp);lineage=root/'lineage';lineage.mkdir()
   for n in ('selection.json','memory-plan.json'):(lineage/n).write_text('{}')
   out=root/'run';out.mkdir();(out/'device-isolation.json').write_text('{"passed":true}')
   identity=dict(lineage=str(lineage),binary='CPU-MOCK-NEVER-EXECUTED',dispatch='mock',timing='token',selection_sha256='mock',lane='B')
   monitor=types.SimpleNamespace(poll=lambda **kw:None,register=lambda *a:None)
   def drain(t,o,success,reason=None):drains.append(success);t.closed=True
   with patch.dict(sys.modules,{'pipeline':pipeline,'suite':suite,'storage':types.SimpleNamespace()}),patch.object(placement,'verify_identity',return_value=({'draft_rank':1,'target_split':0},memory)),patch.object(worker,'DeviceMonitor',return_value=monitor),patch.object(worker,'masked_environment',return_value={}),patch.object(worker,'drain',side_effect=drain):
    result=worker.run(identity,out,1800)
   if corrupt:
    self.assertEqual(result,1);self.assertEqual(drains,[False]);self.assertTrue((out/'failure.json').is_file())
    self.assertEqual(calls[-1],('architecture-tradeoff',64))
   else:
    self.assertEqual(result,0);self.assertEqual(calls,[(i,64) for i in ids]);self.assertEqual(drains,[True])
    self.assertEqual(resets,[i+'64' for i in ids]+['after-suite'])
    proof=json.loads((out/'report-inputs.json').read_text());self.assertEqual(len(proof['requests']),12)
    self.assertEqual(next(r for r in proof['requests'] if r['prompt_id']=='architecture-tradeoff')['tokens'][30],215495)
 def test_all_prompts_and_resets(self):self.exercise()
 def test_old_device_mismatch_stops_smoke(self):self.exercise(corrupt=True)

if __name__=='__main__':unittest.main()
