"""Actual finite client+campaign with CPU-only synthetic transport and filesystem."""
import asyncio
import importlib.util
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import test_request_client as T
spec=importlib.util.spec_from_file_location('campaign_tested111',HERE/'campaign.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)


class Backend:
    def __init__(self, fixture):
        self.f=fixture;self.completed=[];self.proofs=[];self.calls=[];self.posts=0;self.defect=None
    def transport(self):
        owner=self
        class IO(T.Transport):
            async def get(self,path):
                if path!='/ltx-resolution/status':
                    result=await super().get(path)
                    if path.startswith('/history/') and self.name not in owner.completed:
                        owner.completed.append(self.name)
                    return result
                owner.f.phase()
                result={'phase':'native_reference','active':None,'halted':None,
                        'completed':list(owner.completed),'proofs':list(owner.proofs),
                        'server_identity_sha256':owner.f.contract['server_identity_sha256'],
                        'runtime_manifest_sha256':owner.f.manifest_sha,
                        'state':{'fault':False,'queue_running':0,'queue_pending':0,
                                 'preview_pending':0,'preview_failures':0,
                                 'pipeline':{'running':0,'stages':{}}}}
                if owner.defect=='fault':result['state']['fault']=True
                if owner.defect=='identity':result['server_identity_sha256']='f'*64
                if owner.defect=='completed':result['completed']=['wrong']
                if owner.defect=='proof':result['proofs']=['invented']
                return result
            async def submit(self,graph,client_id):
                owner.posts+=1
                result=await super().submit(graph,client_id)
                self.name=self.pid.removeprefix('synthetic-');owner.calls.append('submit:'+self.name)
                return result
            async def action(self,action):
                owner.calls.append(action)
                if owner.defect=='action':raise OSError('uncertain action response')
                if action.startswith('verify:'):
                    owner.proofs.append(action.split(':',1)[1])
                return {'passed':True,'action':action,'phase':'native_reference','proof_sha256':'e'*64}
        return IO()


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.f=T.ClientControls();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.backend=Backend(self.f)
        self.campaign=M.Campaign(self.f.client,self.backend.transport)
    def run_campaign(self):return asyncio.run(self.campaign.run())

    def test_eight_sequence_each_proof_then_final_no_lifecycle(self):
        result=self.run_campaign()
        expected=[]
        for name in self.f.client.ordered_names:expected.extend(['submit:'+name,'verify:'+name])
        self.assertEqual(self.backend.calls,expected+['verify-final'])
        self.assertEqual(self.backend.posts,8)
        self.assertTrue(result['application_retained'])
        self.assertEqual(self.f.client.state['verified'],self.f.client.ordered_names)
        self.assertEqual(len(list((self.f.root/'requests').iterdir())),8)
        with self.assertRaises(RuntimeError):self.run_campaign()
        self.assertEqual(self.backend.posts,8)
        self.assertFalse((self.f.client_dir/'HALT.json').exists())

    def test_bad_status_before_first_submit_halts(self):
        for defect in ('identity','completed','proof','fault'):
            f=T.ClientControls();f.setUp()
            try:
                b=Backend(f);b.defect=defect
                with self.assertRaises(RuntimeError):asyncio.run(M.Campaign(f.client,b.transport).run())
                self.assertEqual(b.posts,0);self.assertTrue((f.client_dir/'HALT.json').exists())
            finally:f.doCleanups()

    def test_uncertain_proof_action_never_retried_or_followed_by_submit(self):
        self.backend.defect='action'
        with self.assertRaises(OSError):self.run_campaign()
        self.assertEqual(self.backend.posts,1)
        self.assertEqual(len(self.backend.calls),2)
        self.assertTrue((self.f.client_dir/'HALT.json').exists())
        self.assertEqual(self.f.client.state['verified'],[])

    def test_idle_requires_complete_real_queue_preview_pipeline_state(self):
        state={'fault':False,'queue_running':0,'queue_pending':0,'preview_pending':0,
               'preview_failures':0,'pipeline':{'running':0,'stages':{}}}
        self.assertTrue(M.is_idle(state))
        for key in ('queue_running','queue_pending','preview_pending','preview_failures'):
            broken=dict(state);broken.pop(key);self.assertFalse(M.is_idle(broken))
            broken=dict(state);broken[key]=False;self.assertFalse(M.is_idle(broken))
        broken=dict(state,pipeline={'running':0,'stages':{'sampler':{'queued_indices':[],
                                  'jobs':[{'done':True,'error':None}]}}})
        self.assertFalse(M.is_idle(broken))

    def test_storage_exhaustion_after_proof_stops_remaining_requests(self):
        original=self.backend.transport
        def factory():
            io=original();action=io.action
            async def bound(action_name):
                result=await action(action_name)
                self.f.free=M.C.MIN_FREE-1
                return result
            io.action=bound
            return io
        self.campaign.transport_factory=factory
        with self.assertRaises(RuntimeError):self.run_campaign()
        self.assertEqual(self.backend.posts,1)
        self.assertTrue((self.f.client_dir/'HALT.json').exists())

    def test_source_contains_no_automatic_lifecycle_api(self):
        import ast
        tree=ast.parse((HERE/'campaign.py').read_text())
        calls=[n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
        self.assertFalse(set(calls)&{'kill','killpg','terminate','send_signal','Popen','system'})

if __name__=='__main__':unittest.main()
