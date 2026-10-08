"""CPU-only integration seams: synthetic owners, no Torch, sockets or runtime build."""
import asyncio
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import sys
import threading
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

M=load('continuation111_integration_tested',HERE/'integration.py')
S=load('continuation111_session_integration_tested',HERE/'session.py')
PLAN=json.loads((HERE.parent/'20261007-continuation111-plan/candidate-plan.json').read_text())['plan']


def quiet():
    return dict(fault=False,queue_running=0,queue_pending=0,preview_pending=0,preview_failures=0,
                pipeline={'running':0,'stages':{}},sampler_routes=0,lean_state=0,decode_replicas=0)


class Fixture:
    def __init__(self,root):
        self.r=M.Runtime.__new__(M.Runtime)
        r=self.r;r.session=S;r.run=root;r.root=root;r.packet=root
        r.manifest_sha='a'*64;r.identity_sha='b'*64
        r.manifest={'model_verification_sha256':'c'*64}
        r.lock=threading.RLock();r.action_busy=False;r.actions_done=set()
        r.provider_seen=set();r.anchor_image=None
        self.events=[];self.writes={};self.fault=False;self.state=quiet()
        self.image=object();self.output=object();self.vae=object();self.latent=object()
        self.binding={'anchor_sha256':'d'*64}
        self.context=None
        r.authority=NS(lock=threading.RLock(),active=None,failed=None,plan=copy.deepcopy(PLAN),
            requests={x['name']:copy.deepcopy(x) for x in PLAN['requests']},proofs={},
            completed=[],request_prompt_ids={},phase='native_reference')
        r.authority.healthy=lambda:S.require(r.authority.failed is None,'halted')
        r.authority.revalidate_proof=self.revalidate
        r.authority.accept_proof=self.accept
        r.fault=lambda:self.fault
        r.inspect_state=lambda:copy.deepcopy(self.state)
        r.storage_check=lambda:self.events.append('storage')
        r.write=self.write
        r.adapter=NS(ready=True,failed=None,current_name=None,guard=object(),receipts=[],
            controller=NS(receipts=[]),before_request=self.before,after_request=self.after,
            abort_request=self.abort,native_state=lambda:{'observation_only':True})
        r.bindings=NS(check_native=lambda:self.events.append('binding-check'),settings=lambda:{},
            anchor_module=NS(load_image=self.load_anchor),torch=object(),tensor_metadata=lambda x:{'id':id(x)},
            receipt=lambda:{'source':'bound'},native_call=object())
        r.conditioning=NS(active=None,anchor=None,failed=None,receipts=[],begin_request=self.begin,
            finish_request=self.finish,run_stage=self.stage)
        r._complete_policy=lambda stages:{'synthetic_policy':True}
        r.capture_guard=NS(receipt=lambda:{'captures_reserved':6,'failed':None})
        r.verifier=NS(produce=self.produce)
    def activate(self,index):
        r=self.r;row=r.authority.requests[PLAN['execution_order'][index]]
        r.authority.active={'name':row['name'],'prompt_id':'prompt-'+str(index)}
        r.authority.request_prompt_ids[row['name']]='prompt-'+str(index)
        r.adapter.current_name=row['name'];return row
    def write(self,name,value):
        S.require(name not in self.writes,'exclusive write')
        self.writes[name]=copy.deepcopy(value);self.events.append('write:'+name)
    def revalidate(self,name):
        self.events.append('revalidate:'+name)
        self.r.authority.proofs[name]={'sha256':'e'*64}
        return {'checked':{'anchor_binding':self.binding}}
    def load_anchor(self,binding,context,torch):
        self.events.append('load-anchor');self.context=context
        S.require(binding is self.binding,'caller binding differs');return self.image
    def begin(self,name,anchor,expected_anchor_sha256):
        self.events.append('conditioning-begin')
        self.r.conditioning.active=name;self.r.conditioning.anchor=anchor
        S.require(anchor is self.image and expected_anchor_sha256=='d'*64,'anchor wrong')
    def stage(self,stage,**kw):
        self.events.append('stage:'+stage)
        S.require(kw['native_call'] is self.r.bindings.native_call,'native binding wrong')
        return self.output
    def finish(self,name):
        self.events.append('conditioning-finish')
        S.require(self.r.anchor_image is self.image,'runtime released anchor early')
        self.r.conditioning.active=None;self.r.conditioning.anchor=None
    def before(self,name):self.events.append('before:'+name);return {'admitted':True}
    def after(self,name):
        self.events.append('after:'+name)
        if self.r.authority.requests[name]['chunk_index']:
            S.require(self.r.anchor_image is self.image,'anchor released before post-memory')
        return {'admitted':True}
    def abort(self,error):
        self.events.append('abort');self.r.adapter.failed=str(error)
        self.r.adapter.guard=None
        raise RuntimeError('synthetic adapter failure latch')
    def produce(self,name):
        self.events.append('produce:'+name)
        return {'verified':True,'name':name}
    def accept(self,name,path,sha):
        self.events.append('accept:'+name)
        self.r.authority.proofs[name]={'sha256':sha}


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.f=Fixture(Path(self.tmp.name));self.r=self.f.r

    def test_provider_binds_same_pass_predecessor_and_one_owned_image(self):
        for index in (3,4,6,7):
            with self.subTest(index=index):
                f=Fixture(Path(self.tmp.name));r=f.r;row=f.activate(index)
                image=r.provide_anchor(row['name'])
                self.assertIs(image,f.image);self.assertIs(r.anchor_image,image)
                self.assertIs(r.conditioning.anchor,image)
                previous=r.authority.requests[row['predecessor_capture']]
                self.assertEqual(f.context['pass_index'],row['pass_index'])
                self.assertEqual(f.context['chunk_index'],row['chunk_index']-1)
                self.assertEqual(f.context['graph_sha256'],previous['graph_sha256'])
                self.assertEqual(f.context['capture_name'],row['predecessor_capture'])
                self.assertEqual(f.context['runtime_manifest_sha256'],r.manifest_sha)
                with self.assertRaises(RuntimeError):r.provide_anchor(row['name'])
                self.assertEqual(f.events.count('load-anchor'),1)

    def test_provider_ordinary_chunk_wrong_request_or_no_scope_refused(self):
        for defect in ('ordinary','wrong-name','scope','fault'):
            f=Fixture(Path(self.tmp.name));row=f.activate(2 if defect=='ordinary' else 3)
            if defect=='scope':f.r.adapter.guard=None
            if defect=='fault':f.fault=True
            name='other' if defect=='wrong-name' else row['name']
            with self.assertRaises(RuntimeError):f.r.provide_anchor(name)
            self.assertNotIn('load-anchor',f.events)

    def test_provider_rechecks_active_and_fault_after_loading_cpu_anchor(self):
        row=self.f.activate(3)
        def load(*args):self.f.fault=True;return self.f.image
        self.r.bindings.anchor_module.load_image=load
        with self.assertRaises(RuntimeError):self.r.provide_anchor(row['name'])
        self.assertNotIn('conditioning-begin',self.f.events)
        self.assertIsNone(self.r.anchor_image)

    def test_condition_preserves_original_return_and_refuses_alias_or_policy(self):
        row=self.f.activate(3);self.r.provide_anchor(row['name'])
        result=self.r.condition(self.f.vae,self.f.image,self.f.latent,1.0,False,row['name'],'A')
        self.assertIs(result,self.f.output)
        for image,strength,bypass,stage in ((object(),1.,False,'A'),(self.f.image,True,False,'A'),
            (self.f.image,.5,False,'A'),(self.f.image,1.,True,'A'),(self.f.image,1.,False,'a')):
            with self.assertRaises(RuntimeError):
                self.r.condition(self.f.vae,image,self.f.latent,strength,bypass,row['name'],stage)
        self.assertEqual(self.f.events.count('stage:A'),1)

    def test_after_keeps_anchor_until_native_postcheck_and_persists_both_receipts(self):
        row=self.f.activate(3);self.r.provide_anchor(row['name'])
        self.r.after_request(row,'prompt-3')
        self.assertLess(self.f.events.index('conditioning-finish'),self.f.events.index('after:'+row['name']))
        self.assertIsNone(self.r.anchor_image)
        self.assertIn('conditioning-receipt-'+row['name']+'.json',self.f.writes)
        self.assertIn('native-memory-after-'+row['name']+'.json',self.f.writes)

    def test_after_missing_provider_or_guard_failure_never_emits_native_success(self):
        row=self.f.activate(3)
        with self.assertRaises(RuntimeError):self.r.after_request(row,'prompt-3')
        self.assertFalse(any(x.startswith('after:') for x in self.f.events))
        self.r.provide_anchor(row['name'])
        def fail(name):raise RuntimeError('incomplete stage B')
        self.r.conditioning.finish_request=fail
        with self.assertRaises(RuntimeError):self.r.after_request(row,'prompt-3')
        self.assertIs(self.r.anchor_image,self.f.image)
        self.assertFalse(any(x.startswith('after:') for x in self.f.events))

    def test_failure_preserves_precontroller_receipts_and_avoids_abort_until_initialized(self):
        row=self.f.activate(1);self.r.adapter.controller=None
        self.r.adapter.receipts=[{'preadmission':'refused'}]
        self.r.on_failure(row,'prompt-1',RuntimeError('no headroom'))
        self.assertNotIn('abort',self.f.events)
        receipt=self.f.writes['continuation-native-failure-'+row['name']+'.json']
        self.assertEqual(receipt['adapter_receipts'],[{'preadmission':'refused'}])
        self.assertEqual(receipt['controller_receipts'],[])

    def test_failure_writes_even_when_abort_latches_and_raises_no_gpu_callback(self):
        row=self.f.activate(3)
        self.r.adapter.native_state=lambda:(_ for _ in ()).throw(AssertionError('GPU observation on failure'))
        self.r.inspect_state=lambda:(_ for _ in ()).throw(AssertionError('state query on failure'))
        with self.assertRaisesRegex(RuntimeError,'synthetic adapter'):
            self.r.on_failure(row,'prompt-3',ValueError('native failed'))
        self.assertEqual(self.f.events[0],'abort')
        self.assertIsNone(self.r.adapter.guard)
        self.assertIn('continuation-native-failure-'+row['name']+'.json',self.f.writes)

    def test_before_requires_ready_owner_no_retained_anchor_and_no_action_overlap(self):
        for defect in ('action','not-ready','anchor'):
            f=Fixture(Path(self.tmp.name));row=f.activate(3)
            if defect=='action':f.r.action_busy=True
            if defect=='not-ready':f.r.adapter.ready=False
            if defect=='anchor':f.r.anchor_image=object()
            with self.assertRaises(RuntimeError):f.r.before_request(row,'prompt-3')
            self.assertFalse(any(x.startswith('before:') for x in f.events))

    def test_node_classes_route_exact_objects_and_original_nodeoutput(self):
        with patch.object(M,'_CTX',self.r):
            row=self.f.activate(3)
            self.assertEqual(M.LTXContinuationAnchor111().apply(row['name']),(self.f.image,))
            out=M.LTXContinuationCondition111().apply(self.f.vae,self.f.image,self.f.latent,1.,False,row['name'],'A')
            self.assertIs(out,self.f.output)
        with patch.object(M,'_CTX',None):
            with self.assertRaises(RuntimeError):M.LTXContinuationAnchor111().apply('name')
        self.assertNotEqual(M.LTXContinuationAnchor111.IS_CHANGED(),M.LTXContinuationAnchor111.IS_CHANGED())

    def test_action_proof_write_precedes_acceptance_and_repeat_refused(self):
        name=PLAN['execution_order'][0]
        self.r.authority.completed=[name];self.r.authority.request_prompt_ids[name]='p0'
        self.r.adapter=None
        result=self.r.action('verify:'+name)
        self.assertTrue(result['passed'])
        self.assertTrue((self.r.run/('continuation-proof-'+name+'.json')).exists())
        self.assertIn(name,self.r.authority.proofs)
        with self.assertRaises(RuntimeError):self.r.action('verify:'+name)
        self.assertEqual(self.f.events.count('produce:'+name),1)

    def test_final_refuses_incomplete_chain_before_any_final_receipt(self):
        with self.assertRaises(RuntimeError):self.r.action('verify-final')
        self.assertNotIn('continuation-final.json',self.f.writes)


class ActionOwnershipTests(unittest.IsolatedAsyncioTestCase):
    def context(self, *, fail=False, halt_write_fails=False):
        started=threading.Event();release=threading.Event();events=[]
        authority=NS(lock=threading.RLock(),failed=None)
        def halt(error):
            with authority.lock:
                events.append('halt')
                authority.failed=str(error)
                if halt_write_fails:raise OSError('synthetic fsync failure')
        authority.halt=halt
        def action(name):
            with authority.lock:
                events.append('worker-start');started.set()
                if not release.wait(2):raise RuntimeError('synthetic test release absent')
                events.append('worker-finish')
                if fail:raise ValueError('proof refused')
                return {'passed':True,'action':name}
        ctx=NS(session=S,authority=authority,action=action,action_busy=False,
               action_worker=None,action_cleanup=None,action_halt_receipt_error=None)
        return ctx,started,release,events

    async def test_cancelled_http_keeps_busy_until_actual_thread_exits_then_halts(self):
        ctx,started,release,events=self.context()
        waiter=asyncio.create_task(M.run_owned_action(ctx,'verify:one'))
        try:
            self.assertTrue(await asyncio.to_thread(started.wait,1))
            waiter.cancel()
            with self.assertRaises(asyncio.CancelledError):await waiter
            await asyncio.sleep(0)
            self.assertTrue(ctx.action_busy)
            self.assertFalse(ctx.action_worker.done())
            self.assertFalse(ctx.action_worker.cancelled())
            self.assertIsNone(ctx.authority.failed)
            # The event loop remains usable while the worker owns authority.lock.
            tick=[];asyncio.get_running_loop().call_soon(tick.append,'alive')
            await asyncio.sleep(0);self.assertEqual(tick,['alive'])
            with self.assertRaises(RuntimeError):await M.run_owned_action(ctx,'verify:two')
        finally:release.set()
        await asyncio.wait_for(ctx.action_cleanup,1)
        self.assertFalse(ctx.action_busy)
        self.assertIn('cancelled',ctx.authority.failed)
        self.assertEqual(events,['worker-start','worker-finish','halt'])
        with self.assertRaises(RuntimeError):await M.run_owned_action(ctx,'verify:one')

    async def test_success_releases_only_completed_worker_without_halt(self):
        ctx,started,release,events=self.context()
        waiter=asyncio.create_task(M.run_owned_action(ctx,'verify:one'))
        try:
            self.assertTrue(await asyncio.to_thread(started.wait,1))
            self.assertTrue(ctx.action_busy);self.assertFalse(waiter.done())
        finally:release.set()
        result=await asyncio.wait_for(waiter,1)
        self.assertTrue(result['passed']);self.assertFalse(ctx.action_busy)
        self.assertTrue(ctx.action_worker.done());self.assertIsNone(ctx.authority.failed)
        self.assertEqual(events,['worker-start','worker-finish'])

    async def test_proof_failure_and_failed_halt_receipt_keep_permanent_refusal(self):
        ctx,started,release,events=self.context(fail=True,halt_write_fails=True)
        release.set()
        with self.assertRaisesRegex(ValueError,'proof refused'):
            await M.run_owned_action(ctx,'verify:one')
        self.assertEqual(ctx.authority.failed,'proof refused')
        self.assertIn('fsync failure',ctx.action_halt_receipt_error)
        self.assertFalse(ctx.action_busy)
        with self.assertRaises(RuntimeError):await M.run_owned_action(ctx,'verify:one')
        self.assertEqual(events,['worker-start','worker-finish','halt'])

    async def test_status_busy_returns_without_taking_authority_lock(self):
        handlers={}
        class Routes:
            def get(self,path):return lambda fn:handlers.setdefault(('GET',path),fn)
            def post(self,path):return lambda fn:handlers.setdefault(('POST',path),fn)
        class NoLock:
            def __enter__(self):raise AssertionError('event loop tried authority lock')
            def __exit__(self,*args):pass
        web=NS(middleware=lambda fn:fn,json_response=lambda value,status=200:(status,value))
        instance=NS(routes=Routes(),app=NS(middlewares=[]))
        ctx=NS(action_busy=True,authority=NS(lock=NoLock()))
        with patch.dict(sys.modules,{'aiohttp':NS(web=web),'server':NS(PromptServer=NS(instance=instance))}), \
             patch.object(M,'_CTX',ctx),patch.object(M,'_ROUTES_INSTALLED',False):
            M.install_routes()
            status,value=await handlers[('GET','/ltx-resolution/status')](None)
            self.assertEqual(status,409);self.assertIn('active',value['error'])


class ProofSerializationTests(unittest.TestCase):
    def test_actual_runtime_action_owns_executor_authority_lock_during_verifier(self):
        with tempfile.TemporaryDirectory() as root:
            f=Fixture(Path(root));r=f.r;name=PLAN['execution_order'][0]
            r.authority.completed=[name];r.authority.request_prompt_ids[name]='p0';r.adapter=None
            def produce(name):
                self.assertTrue(r.authority.lock._is_owned())
                return {'name':name,'verified':True}
            r.verifier.produce=produce
            self.assertTrue(r.action('verify:'+name)['passed'])
            self.assertFalse(r.authority.lock._is_owned())

if __name__=='__main__':unittest.main()
