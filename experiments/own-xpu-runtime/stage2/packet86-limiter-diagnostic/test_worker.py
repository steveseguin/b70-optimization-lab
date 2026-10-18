import tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import worker as tp2_worker
import types
from common import D, P56, module, read, save

class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)

    def test_full_worker_mock_incident_then_twelve_requests_and_drain(self):
        import sys
        sys.path.insert(0,str(P56))
        self.addCleanup(lambda:sys.path.remove(str(P56)))
        import pipeline,suite,storage
        entries=[dict(prompt_id=p) for p in D.CHECK.PROMPT_IDS]
        snapshots={e['prompt_id']:(self.root,[1,2,3]) for e in entries}
        calls=[]
        output=self.root/'run'
        test=self
        class Transport:
            def __init__(self,*a,**kw):calls.append('load')
            def call(self,rank,op,**kwargs):calls.append(('reset-mode',kwargs.get('token',0)))
            def close(self,success):
                test.assertTrue((output/'report-inputs.json').exists())
                test.assertFalse((output/'summary.json').exists())
                calls.append(('close',success))
        def reset(t,path):
            path.mkdir(parents=True);calls.append(('reset',path.name))
            t.call(0, suite.RESET);t.call(1, suite.RESET)
        def request(t,args,prompt,count):
            calls.append(('request',count))
            return dict(tokens=list(range(count)),passed=True,prompt_tokens=3)
        def monitor(lane,output):
            def poll(**kw):save(output/'device-isolation.json',dict(passed=True))
            return types.SimpleNamespace(poll=poll,register=lambda pid:None)
        lineage=self.root/'exp-nodeq';lineage.mkdir()
        for name in ('selection.json','memory-plan.json'):(lineage/name).write_bytes((P56/name).read_bytes())
        seal=lineage/'screen-seal.json';save(seal,dict(diagnostic_nonexact=True))
        identity=dict(seal=str(seal),lineage=str(lineage),binary='/mock',dispatch='/mock',selection_sha256='a'*64,
                      lane='B',timing='attribution',binary_sha256='b'*64,placement=dict(draft_rank=1,target_split=0,target_layers=[24,24]))
        old=(pipeline.P,storage.P,storage.B,storage.admit)
        try:
            with patch.object(D,'oracle_inputs',return_value={'prompts':entries}),patch.object(D.CHECK,'token_record',return_value=[999]*128),patch.object(pipeline,'Transport',Transport),patch.object(suite,'checker_module'),patch.object(suite,'admit_inputs',return_value=snapshots),patch.object(suite,'reset',side_effect=reset),patch.object(suite,'run_request',side_effect=request),patch('placement.verify_identity',return_value=(identity['placement'],module('mock_memory',P56/'memory_gate.py'))),patch.object(tp2_worker,'summary',side_effect=AssertionError('worker must not report')),patch.object(tp2_worker,'Teardown'),patch.object(tp2_worker,'masked_environment',return_value={}),patch.object(tp2_worker,'DeviceMonitor',side_effect=monitor):
                self.assertEqual(tp2_worker.run(identity,self.root/'run',3600),0)
        finally:
            pipeline.P,storage.P,storage.B,storage.admit=old
        self.assertEqual([c for c in calls if isinstance(c,tuple) and c[0]=='request'],[('request',64)]+[('request',128)]*24)
        self.assertEqual(calls[-1],('close',True))
        self.assertTrue(read(self.root/'run/report-inputs.json')['passed'])
        self.assertEqual(len(read(self.root/'run/paired-inputs.json')['arms']['control']),12)
        self.assertEqual(len(read(self.root/'run/paired-inputs.json')['arms']['attribution']),12)
        self.assertEqual([c[1] for c in calls if isinstance(c,tuple) and c[0]=='reset-mode'][:50], [1]*26+[0]*24)
        self.assertFalse((self.root/'run/summary.json').exists())
        rows=read(output/'paired-inputs.json')['arms']['attribution']
        self.assertTrue(all(not r['exact_oracle'] and r['outcome']=='diagnostic_output_mismatch' and r['diagnostic_nonexact'] for r in rows))
