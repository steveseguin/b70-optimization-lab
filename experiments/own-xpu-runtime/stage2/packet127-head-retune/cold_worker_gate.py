"""Execute the copied worker with mock transport: exactly twelve cold requests."""
import contextlib,json,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parent
from bootstrap import install
install()
import runtime_worker as worker
from common import D,P56,module,read,save
from build_engine import ROOT,sha

class ColdWorker(unittest.TestCase):
 def test_twelve_requests_and_same_response_canary(self):
  import chain_pipeline as pipeline,suite,storage,memory_observation
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);output=root/'run';entries=[dict(prompt_id=p) for p in D.CHECK.PROMPT_IDS]
   snapshots={e['prompt_id']:(root,[i+1,2,3]) for i,e in enumerate(entries)};calls=[];test=self
   class Transport:
    def __init__(self,*a,**kw):calls.append('load')
    def close(self,success):
     test.assertTrue((output/'report-inputs.json').exists());calls.append(('close',success))
   def reset(t,path):path.mkdir();calls.append(('reset',path.name))
   def request(t,args,prompt,count):
    calls.append(('request',prompt[0],count));return dict(tokens=list(range(count)),passed=True,prompt_tokens=3)
   def monitor(lane,output):
    def poll(**kw):save(output/'device-isolation.json',dict(passed=True))
    return types.SimpleNamespace(poll=poll,register=lambda pid:None)
   identity=dict(lineage=str(P),binary='/mock',dispatch='/mock',selection_sha256='a'*64,lane='A',timing='token',placement=dict(draft_rank=1,target_split=0))
   old=(pipeline.P,storage.P,storage.B,storage.admit)
   try:
    with patch.object(D,'oracle_inputs',return_value={'prompts':entries}),patch.object(D.CHECK,'token_record',return_value=list(range(128))),patch.object(pipeline,'Transport',Transport),patch.object(suite,'checker_module'),patch.object(suite,'admit_inputs',return_value=snapshots),patch.object(suite,'reset',side_effect=reset),patch.object(suite,'run_request',side_effect=request),patch('placement.verify_identity',return_value=(identity['placement'],module('p127_mock_memory',P/'memory_gate.py'))),patch.object(worker,'summary',side_effect=AssertionError('worker must not report')),patch.object(worker,'Teardown'),patch.object(worker,'masked_environment',return_value={}),patch.object(worker,'DeviceMonitor',side_effect=monitor),patch.object(memory_observation,'capture') as capture:
     self.assertEqual(worker.run(identity,output,3600),0)
    self.assertEqual([c for c in calls if isinstance(c,tuple) and c[0]=='request'],[('request',i+1,128) for i in range(12)])
    self.assertEqual(calls[-1],('close',True));self.assertEqual(capture.call_count,2)
    proof=read(output/'report-inputs.json');incident=proof['incident64'];first=output/entries[0]['prompt_id']/'receipt.json'
    self.assertEqual(len(proof['requests']),12);self.assertEqual(incident['mode'],'first-64-of-first-cold-128-response')
    self.assertEqual(incident['receipt_sha256'],sha(first));self.assertEqual(incident['prompt_id'],entries[0]['prompt_id'])
   finally:pipeline.P,storage.P,storage.B,storage.admit=old

if __name__=='__main__':
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ColdWorker))
 report=P/'evidence/protocol-tests.json';row=json.loads(report.read_text());row['cold_worker_passed']=result.wasSuccessful();row['passed']=row['passed'] and result.wasSuccessful()
 row['sources'].update({str(f.relative_to(ROOT)):sha(f) for f in (P/'cold_worker_gate.py',P/'runtime_worker.py')});report.write_text(json.dumps(row,indent=2)+'\n')
 raise SystemExit(0 if result.wasSuccessful() else 1)
