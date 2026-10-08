"""Synthetic CPU transport controls. No sockets, procfs or devices."""
import asyncio
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('request_client_tested111', HERE/'request_client.py')
C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)
PLAN = HERE.parent/'20261007-continuation111-plan/candidate-plan.json'

class Transport:
    def __init__(self, mode=None, hook=None):
        self.mode = mode; self.hook = hook; self.posts = 0; self.polls = 0; self.events = []
        self.closed = False

    async def __aenter__(self): return self
    async def __aexit__(self, *args): self.closed = True
    async def subscribe(self, client_id): self.client_id = client_id

    async def get(self, path):
        if path == '/queue':
            return {'queue_running': [], 'queue_pending': ['other'] if self.mode == 'busy' else []}
        self.polls += 1
        if self.mode == 'history-delay' and self.polls < 3: return {}
        history = {'prompt': [1, self.pid, self.graph], 'status': self.status}
        if self.mode == 'wrong-history': history['prompt'][2] = {}
        return {self.pid: history}

    async def submit(self, graph, client_id):
        self.posts += 1; self.graph = copy.deepcopy(graph)
        names = {n['inputs']['run_name'] for n in graph.values() if 'run_name' in n['inputs']}
        self.pid = 'synthetic-' + names.pop()
        if self.mode == 'submit-error': raise OSError('transport submission uncertain')
        start = int(time.time()*1000); end = start + 1
        first = {'type': 'execution_start', 'data': {'prompt_id': self.pid, 'timestamp': start}}
        last = {'type': 'execution_success', 'data': {'prompt_id': self.pid, 'timestamp': end}}
        self.events = [first, last]
        messages = [[e['type'], e['data']] for e in self.events]
        self.status = {'status_str': 'success', 'completed': True, 'messages': messages}
        if self.mode == 'stale-terminal': self.events = [last]
        if self.mode == 'stale-start': first['data']['timestamp'] = 1
        if self.mode == 'cached': self.events.insert(1, {'type':'execution_cached','data':{'prompt_id':self.pid,'nodes':['344']}})
        if self.mode == 'error': self.events[-1] = {'type':'execution_error','data':{'prompt_id':self.pid}}
        if self.mode == 'other-events': self.events.insert(0, {'type':'execution_success','data':{'prompt_id':'other'}})
        if self.hook: self.hook()
        return {'prompt_id': self.pid, 'number': 1, 'node_errors': {}}

    async def receive(self, timeout):
        if self.mode == 'timeout':
            await asyncio.sleep(timeout); raise asyncio.TimeoutError()
        return self.events.pop(0)


class ClientControls(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.run=self.root/'server';self.run.mkdir()
        (self.root/'requests').mkdir();self.path=self.root/'contract.json';self.client_dir=self.root/'client'
        self.manifest=self.root/'manifest.json';self.write(self.manifest,{'synthetic':'runtime'})
        self.manifest_sha=C.sha(self.manifest.read_bytes())
        self.identity={'pid':123,'proc_start_ticks':'456','boot_id':'synthetic',
                       'model_verification_sha256':C.MODEL_SHA,'source_packet_manifest_sha256':self.manifest_sha,
                       'server_args_sha256':'b'*64}
        self.write(self.run/'server-identity.json',self.identity)
        guard=self.root/'guard.py';guard.write_text('# synthetic sealed source fixture\n')
        plan=json.loads(PLAN.read_text())['plan']
        self.contract={'schema':'ltx.continuation111-request-client.v1','plan_sha256':C.PLAN_SHA,
                       'root':str(self.root),'server_run':str(self.run),'allowed_names':plan['execution_order'],
                       'client_dir':str(self.client_dir),'plan_path':str(PLAN),
                       'runtime_manifest_path':str(self.manifest),'runtime_manifest_sha256':self.manifest_sha,
                       'server_identity_sha256':C.sha((self.run/'server-identity.json').read_bytes()),
                       'min_free_bytes':C.MIN_FREE,'planned_write_bytes':C.WRITE_ALLOWANCE,
                       'max_captures':6,'max_attempts':8,'request_timeout_seconds':10,'capture_guard_path':str(guard),
                       'phase_observation_path':str(self.run/'resolution-client-phase.json'),
                       'source_bindings':{str(p.resolve()):C.sha(p.read_bytes()) for p in
                                          [guard,HERE/'request_client.py',HERE/'campaign.py']}}
        self.free=60*1024**3;self.proc_calls=0;self.process_ok=True
        self.phase();self.client=self.make_client();self.name=self.client.ordered_names[0]

    def write(self,path,obj):path.write_text(json.dumps(obj)+'\n')
    def phase(self,**changes):
        value={'schema':'ltx.resolution-client-phase.v1','phase':'native_reference',
               'plan_sha256':C.PLAN_SHA,'qualification_id':C.QUALIFICATION_ID,
               'runtime_manifest_sha256':self.manifest_sha,
               'server_identity_sha256':self.contract['server_identity_sha256'],
               'active_request':None,'fault':False,'observed_at_ms':time.time_ns()//1000000}
        value.update(changes);self.write(self.run/'resolution-client-phase.json',value)
    def process(self,identity):
        self.proc_calls+=1;C.require(self.process_ok,'Synthetic reused PID')
    def make_client(self):
        self.write(self.path,self.contract)
        return C.Client(self.path,C.sha(self.path.read_bytes()),process_probe=self.process,free_probe=lambda _:self.free)
    def execute(self,t,name=None):return asyncio.run(self.client.execute(name or self.name,t))

    def test_success_durable_artifacts_and_duplicate_refusal(self):
        t=Transport();result=self.execute(t)
        self.assertEqual(t.posts,1);self.assertEqual(result['name'],self.name)
        for n in ('prompt.json','submission.json','history.json','result.json','events.jsonl','identity.json'):
            self.assertTrue((self.root/'requests'/self.name/n).is_file())
        with self.assertRaises(RuntimeError):self.execute(t)
        self.assertEqual(t.posts,1);self.assertTrue((self.client_dir/'HALT.json').exists())

    def test_wrong_graph_order_and_missing_proof_before_post(self):
        for case in ('graph','order','proof'):
            with self.subTest(case=case):
                f=ClientControls();f.setUp()
                try:
                    t=Transport();name=f.name
                    if case=='graph':f.client.rows[name]['graph']={}
                    if case=='order':name=f.client.ordered_names[1]
                    if case=='proof':
                        f.execute(Transport());name=f.client.ordered_names[1]
                    with self.assertRaises(RuntimeError):f.execute(t,name)
                    self.assertEqual(t.posts,0)
                finally:f.doCleanups()

    def test_phase_stale_fault_wrong_identity_before_post(self):
        for changes in ({'observed_at_ms':1},{'fault':True},{'active_request':'other'},
                        {'phase':'timing'},{'server_identity_sha256':'e'*64}):
            f=ClientControls();f.setUp()
            try:
                f.phase(**changes);t=Transport()
                with self.assertRaises(RuntimeError):f.execute(t)
                self.assertEqual(t.posts,0)
            finally:f.doCleanups()

    def test_process_source_contract_manifest_and_fault_drift(self):
        for defect in ('process','source','contract','manifest','fault'):
            f=ClientControls();f.setUp()
            try:
                if defect=='process':f.process_ok=False
                if defect=='source':(f.root/'guard.py').write_text('changed')
                if defect=='contract':f.path.write_text('{}')
                if defect=='manifest':f.manifest.write_text('{}')
                if defect=='fault':(f.root/'FAULT.json').write_text('{}')
                t=Transport()
                with self.assertRaises(RuntimeError):f.execute(t)
                self.assertEqual(t.posts,0)
            finally:f.doCleanups()

    def test_storage_floor_before_output_and_charged_budget(self):
        self.free=C.MIN_FREE+C.WRITE_ALLOWANCE-1
        with self.assertRaises(RuntimeError):self.execute(Transport())
        self.assertFalse(self.client_dir.exists())
        self.free=C.MIN_FREE+C.WRITE_ALLOWANCE
        t=Transport(hook=lambda:setattr(self,'free',C.MIN_FREE-1))
        with self.assertRaises(RuntimeError):self.execute(t)
        self.assertEqual(t.posts,1);self.assertTrue((self.client_dir/'HALT.json').exists())

    def test_submission_and_execution_failures_no_retry(self):
        for mode in ('submit-error','wrong-history','stale-terminal','stale-start','cached','error','busy'):
            f=ClientControls();f.setUp()
            try:
                t=Transport(mode)
                with self.assertRaises(Exception):f.execute(t)
                self.assertEqual(t.posts,0 if mode=='busy' else 1)
                self.assertTrue((f.client_dir/'HALT.json').exists())
            finally:f.doCleanups()

    def test_contract_caps_and_allowed_names_fail_closed(self):
        for key,value in [('max_captures',7),('max_attempts',9),('planned_write_bytes',1),
                          ('request_timeout_seconds',True),('allowed_names',[])]:
            self.contract[key]=value
            with self.assertRaises(RuntimeError):self.make_client()
            self.setUp()

    def test_process_change_after_submission_keeps_uncertain_evidence(self):
        t=Transport(hook=lambda:setattr(self,'process_ok',False))
        with self.assertRaises(RuntimeError):self.execute(t)
        self.assertEqual(t.posts,1)
        self.assertTrue((self.root/'requests'/self.name/'submission.json').exists())
        self.assertTrue((self.client_dir/'HALT.json').exists())

    def test_receive_timeout_has_one_submit_and_preserves_halt(self):
        original_clock=C.time.monotonic
        offset=[0]
        class TimeoutTransport(Transport):
            async def receive(self,timeout):
                offset[0]=2000
                raise asyncio.TimeoutError('synthetic receive timeout')
        t=TimeoutTransport()
        with patch.object(C.time,'monotonic',side_effect=lambda:original_clock()+offset[0]):
            with self.assertRaises(RuntimeError):self.execute(t)
        self.assertEqual(t.posts,1)
        self.assertTrue((self.client_dir/'HALT.json').exists())
        self.assertTrue((self.root/'requests'/self.name/'submission.json').exists())

if __name__=='__main__':unittest.main()
