"""CPU integration controls against real authority/schedule/gates; no live runtime imports."""
import asyncio
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent

def load(name,file):
    spec=importlib.util.spec_from_file_location(name,HERE/file)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

I=load('integration_tested','integration.py')
SCHEDULE=load('schedule_for_integration','schedule.py')
GATES=load('setup_for_integration','setup_gates.py')
REF=load('reference_for_integration','reference_gate.py')
CAND=load('candidate_for_integration','candidate_gate.py')
GUARD=load('guard_for_integration','executor_guard.py')
SAFETY=load('safety_for_integration','native_safety.py')


class IntegrationControls(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.run=self.root/'run';self.run.mkdir()
        self.packet=self.root/'packet';(self.packet/'resolution').mkdir(parents=True)
        (self.packet/'resolution/candidate-plan.json').write_bytes(SCHEDULE.read(SCHEDULE.PLAN))
        (self.run/'server-identity.json').write_text('{"synthetic":"CPU-only"}\n')
        self.session=load('fresh_integration_authority','session.py')
        self.state={'queue_running':0,'queue_pending':0,'queue_running_ids':[],'queue_pending_ids':[],
            'pipeline':{'running':0,'stages':{}},'fault':False,'sampler_routes':0,'lean_state':0,
            'decode_replicas':0,'captures_frozen':False,'loads_frozen':False}
        observer=types.SimpleNamespace(actual_state=lambda fault=False:dict(copy.deepcopy(self.state),fault=fault))
        self.modules=patch.dict('sys.modules',{'ltx_resolution_session':self.session,'schedule':SCHEDULE,
            'runtime_observer':observer,'reference_gate':REF,'candidate_gate':CAND,'setup_gates':GATES,'native_safety':SAFETY})
        self.modules.start();self.addCleanup(self.modules.stop)
        self.disk=patch.object(I.shutil,'disk_usage',return_value=types.SimpleNamespace(free=64*2**30))
        self.disk.start();self.addCleanup(self.disk.stop)
        self.manifest=json.loads(SCHEDULE.read(SCHEDULE.PARENT/'manifest.json'))
        self.manifest['resolution101']={'parent_manifest_sha256':SCHEDULE.PARENT_SHA}
        self.r=I.Runtime(self.packet,self.manifest,'a'*64,self.run)
        self.rows=self.r.authority.plan['requests']

    def setup_row(self,kind):return next(v for v in self.r.setup.values() if v['kind']==kind)

    def adapter(self):
        controller=types.SimpleNamespace(failed=None,receipts=[])
        objects={key:types.SimpleNamespace() for key in ('video_vae','audio_vae')}
        for obj in objects.values():setattr(obj,SAFETY.ATTRIBUTE,controller)
        seen=[]
        def before(name):
            self.assertEqual(self.r.authority.active['name'],name);seen.append(('before',name));return {'admitted':True}
        def after(name):seen.append(('after',name));return {'admitted':True}
        a=types.SimpleNamespace(ready=True,failed=None,controller=controller,objects=objects,receipts=[],
            native_state=lambda:{'observation_only':True},before_request=before,after_request=after,
            abort_request=lambda error:seen.append(('abort',str(error))),close=lambda:seen.append(('close',)))
        self.r.adapter=a;return a,seen

    def test_actual_pinned_schedule_registered_and_init_no_models(self):
        self.assertEqual(len(self.r.authority.requests),71)
        self.assertEqual(self.r.authority.phase,'native_reference')
        self.assertEqual(self.r.schedule['raw_capture_requests'],64)
        self.assertIsNone(self.r.adapter)

    def test_dependencies_cannot_be_bypassed_or_mutated(self):
        row=self.setup_row('prepare-native');saved=copy.deepcopy(row)
        with self.assertRaisesRegex(RuntimeError,'incomplete'):self.r.require_dependencies(row)
        self.r.authority.completed.append(self.setup_row('window-probe')['name'])
        self.r.require_dependencies(row);self.r.require_dependencies(row)
        self.assertEqual(row,saved)
        with self.assertRaisesRegex(RuntimeError,'barrier missing'):self.r.require_dependencies(self.setup_row('pin0'))

    def test_native_before_observation_is_quiescent_and_real_schema(self):
        self.adapter();self.r.authority.completed.append(self.setup_row('prepare-native')['name'])
        self.r.action('before-native')
        value=json.loads((self.run/'native-before.json').read_text())
        self.assertEqual(value['queue_running'],[])
        self.assertGreater(REF.native_state(value,self.r.identity_sha,SCHEDULE.QUALIFICATION_ID),0)
        self.assertIn('before-native',self.r.actions_done)
        self.assertIsNone(self.r.authority.active)

    def test_running_prompt_refuses_before_native_observation(self):
        self.adapter();self.r.authority.completed.append(self.setup_row('prepare-native')['name'])
        self.state.update(queue_running=1,queue_running_ids=['active'])
        with self.assertRaisesRegex(RuntimeError,'queue is not empty'):self.r.action('before-native')
        self.assertFalse((self.run/'native-before.json').exists())

    def test_native_executor_hooks_bracket_request_and_preserve_failure(self):
        a,seen=self.adapter();self.r.actions_done.add('before-native')
        self.r.authority.completed.append(self.setup_row('prepare-native')['name'])
        class Executor:
            def __init__(self):self.server=types.SimpleNamespace(client_id=None)
            def add_message(self,event,data,broadcast):self.status_messages.append((event,data))
            async def execute_async(this,prompt,pid,extra,outputs):
                this.add_message('execution_start',{'prompt_id':pid},False)
                this.add_message('execution_success',{'prompt_id':pid},False)
        GUARD.install(Executor,self.r.authority,self.r.before_request,self.r.after_request,self.r.on_failure)
        e=Executor();row=self.rows[0]
        asyncio.run(e.execute_async(row['graph'],'cpu-native'))
        self.assertTrue(e.success);self.assertEqual(seen,[('before',row['name']),('after',row['name'])])
        self.assertIn(row['name'],self.r.authority.completed)
        self.assertTrue((self.run/('native-memory-after-'+row['name']+'.json')).is_file())
        row=self.rows[1]
        def fail(name):raise RuntimeError('synthetic post-memory failure')
        a.after_request=fail
        asyncio.run(e.execute_async(row['graph'],'cpu-native-fail'))
        self.assertFalse(e.success);self.assertNotIn(row['name'],self.r.authority.completed)
        self.assertEqual(seen[-1],('abort','synthetic post-memory failure'))
        self.assertTrue((self.run/'resolution-halt.json').exists())

    def test_negative_setup_ui_verdict_not_accepted(self):
        row=self.setup_row('freeze')
        data={'run_name':row['name'],'server_identity_sha256':self.r.identity_sha,
              'model_verification_sha256':GATES.MODEL_SHA,'output_size':'640x384',
              'schema':'ltx.sampler-capture-freeze.v2','outcome':'chain-check-failed',
              'frozen':False,'loads_frozen':False}
        (self.run/('sampler-capture-freeze-'+row['name']+'.json')).write_text(json.dumps(data))
        with self.assertRaisesRegex(RuntimeError,'not frozen'):self.r.after_request(row,'cpu')
        self.assertFalse((self.run/('resolution-setup-accepted-'+row['name']+'.json')).exists())

    def test_prepare_native_passes_exact_source_and_baseline_runtime_inventory(self):
        captured={}
        class Adapter:
            def __init__(self,**kwargs):captured.update(kwargs);self.receipts=[]
            def prepare(self):return {'synthetic':True}
        row=self.setup_row('prepare-native')
        self.r.authority.begin(row['name'],row['graph'],'cpu-prepare')
        mm=types.ModuleType('comfy.model_management');comfy=types.ModuleType('comfy');comfy.model_management=mm
        with patch.dict('sys.modules',{'torch':types.ModuleType('torch'),'nodes':types.ModuleType('nodes'),
            'comfy':comfy,'comfy.model_management':mm,'native_adapter':types.SimpleNamespace(NativeAdapter=Adapter)}):
            self.r.prepare_native(row['name'])
        for path,sha in self.manifest['runtime']['files'].items():self.assertEqual(captured['source_hashes'][path],sha)
        path='source/comfy/model_management.py'
        self.assertEqual(captured['source_hashes'][str(self.packet/path)],self.manifest['files'][path])
        self.assertEqual(captured['runtime_sha256'],'a'*64)

    def capture_evidence(self, worker=0):
        row=self.setup_row('capture%d'%worker);index=row['clip_index']
        self.r.authority.completed.append(row['name'])
        self.r.authority.phase='optimized_preparation';self.r.authority.references_sha='c'*64
        observation={'role':'auxiliary','run_name':None,'phase':'optimized_preparation',
            'plan_sha256':SCHEDULE.PLAN_SHA,'qualification_id':SCHEDULE.QUALIFICATION_ID,
            'comparison_mode':'same-size-native-v1','runtime_manifest_sha256':'a'*64,
            'server_identity_sha256':self.r.identity_sha,'reference_receipt_sha256':'c'*64}
        done={'stage':'sample','index':index,'finished_unix':10.,'finite':True,
              'output_size':'640x384','speed_only':False,'output_parity_claimed':False,
              'session_observation':observation}
        (self.run/('pipeline-done-sample-%d.json'%index)).write_text(json.dumps(done))
        request={'schema':'ltx.pipeline-sampler-request.v1','run_name':row['name'],
            'server_identity_sha256':self.r.identity_sha,'clip_index':index,
            'pinned_worker':'ltx-sample-%d'%worker,'sampler_workers':2,'sampler_batch':1,
            'mode':'pipeline','depth':1,'detail':{'emitted_index':-1,'fill':True},
            'phase_authorization':dict(observation,role='sampler',run_name=row['name'])}
        path=self.run/('pipeline-sampler-'+row['name']+'.json');path.write_text(json.dumps(request))
        self.state['pipeline']={'running':0,'stages':{'sample':{'queued_indices':[],
            'jobs':[{'index':index,'target':'ltx-sample-%d'%worker,'done':True,'error':None}]}}}
        return row,path,request

    def torch_stub(self,free=(8,12,10,14)):
        seen=[]
        xpu=types.SimpleNamespace(synchronize=lambda i:seen.append(i),
            mem_get_info=lambda i:(free[i]*2**30,32*2**30))
        return types.SimpleNamespace(xpu=xpu),seen

    def test_capture_tail_actual_done_and_request_schemas_both_workers(self):
        for worker in (0,1):
            with self.subTest(worker=worker):
                row,path,request=self.capture_evidence(worker)
                retired=[];torch,seen=self.torch_stub()
                with patch.object(self.r,'retire_tails',side_effect=lambda name:retired.append(name)), \
                     patch.dict('sys.modules',{'torch':torch}):
                    self.r.action(row['retirement_action'])
                self.assertEqual(retired,[row['retirement_action']])
                self.assertEqual(seen,list(range(4)))
                memory=json.loads((self.run/('resolution-memory-after-'+row['kind']+'.json')).read_text())
                self.assertEqual(memory['minimum_bytes'],2*2**30)

    def test_wrong_capture_worker_receipt_or_live_target_cannot_retire(self):
        row,path,request=self.capture_evidence(1)
        request['pinned_worker']='ltx-sample-0';path.write_text(json.dumps(request))
        with patch.object(self.r,'retire_tails') as retire:
            with self.assertRaisesRegex(RuntimeError,'worker or phase'):self.r.action(row['retirement_action'])
            retire.assert_not_called()
            request['pinned_worker']='ltx-sample-1';path.write_text(json.dumps(request))
            self.state['pipeline']['stages']['sample']['jobs'][0]['target']='ltx-sample-0'
            with self.assertRaisesRegex(RuntimeError,'live job'):self.r.action(row['retirement_action'])
            retire.assert_not_called()
        self.assertNotIn(row['retirement_action'],self.r.actions_done)

    def test_capture_postflight_memory_floor_refuses_before_retirement(self):
        row,path,request=self.capture_evidence(0);torch,seen=self.torch_stub((8,12,1,14))
        with patch.object(self.r,'retire_tails') as retire,patch.dict('sys.modules',{'torch':torch}):
            with self.assertRaisesRegex(RuntimeError,'Post-capture physical'):self.r.action(row['retirement_action'])
            retire.assert_not_called()
        self.assertEqual(seen,list(range(4)))
        self.assertTrue((self.run/'resolution-memory-after-capture0.json').exists())
        self.assertNotIn(row['retirement_action'],self.r.actions_done)

    def test_pin_receipts_use_pinned_graph_worker_identity(self):
        for worker in (0,1):
            row=self.setup_row('pin%d'%worker)
            receipt={'server_identity_sha256':self.r.identity_sha,'outcome':'pinned',
                'worker':worker,'worker_name':'ltx-sample-%d'%worker,'sampler_workers':2,
                'sampler_batch':1,'output_size':'640x384'}
            path=self.run/('sampler-pin-'+row['name']+'.json');path.write_text(json.dumps(receipt))
            self.r.after_request(row,'cpu')
            receipt['worker']=1-worker;path.write_text(json.dumps(receipt))
            with self.assertRaisesRegex(RuntimeError,'Worker pin'):self.r.after_request(row,'cpu')

    def test_unfinished_tail_not_retired(self):
        self.state['pipeline']={'running':1,'stages':{}}
        with self.assertRaisesRegex(RuntimeError,'still executing'):self.r.retire_tails('synthetic')
        self.assertFalse((self.run/'resolution-tails-synthetic.json').exists())

    def test_optimized_actual_freeze_required_and_storage_floor(self):
        row=self.rows[20];self.r.authority.completed.append(self.setup_row('freeze')['name'])
        with self.assertRaisesRegex(RuntimeError,'not frozen'):self.r.before_request(row,'cpu')
        self.state.update(captures_frozen=True,loads_frozen=True);self.r.before_request(row,'cpu')
        with patch.object(I.shutil,'disk_usage',return_value=types.SimpleNamespace(free=49*2**30)):
            with self.assertRaisesRegex(RuntimeError,'storage allowance'):self.r.storage_check()

    def routes(self):
        handlers={}
        class Routes:
            def get(self,path):
                def register(fn):handlers[('GET',path)]=fn;return fn
                return register
            def post(self,path):
                def register(fn):handlers[('POST',path)]=fn;return fn
                return register
        web=types.SimpleNamespace(middleware=lambda fn:fn,json_response=lambda body,**kw:body)
        instance=types.SimpleNamespace(routes=Routes(),app=types.SimpleNamespace(middlewares=[]))
        with patch.object(I,'_CTX',self.r),patch.dict('sys.modules',{
            'aiohttp':types.SimpleNamespace(web=web),'server':types.SimpleNamespace(PromptServer=types.SimpleNamespace(instance=instance))}):
            I.install_routes()
        return handlers

    def test_status_observation_matches_actual_client_across_all_phases(self):
        client_module=load('integration_actual_client','request_client.py')
        client=object.__new__(client_module.Client);client.full_schedule=True
        client.contract={'phase_observation_path':str(self.run/'resolution-client-phase.json'),
            'runtime_manifest_sha256':'a'*64,'server_identity_sha256':self.r.identity_sha}
        handlers=self.routes()
        with patch.object(I,'_CTX',self.r):
            for phase,row in [('native_reference',self.setup_row('window-probe')),
                              ('optimized_preparation',self.setup_row('pin0')),('timing',self.rows[34])]:
                self.r.authority.phase=phase
                self.r.authority.references_sha=None if phase=='native_reference' else 'c'*64
                self.r.authority.candidate_sha='d'*64 if phase=='timing' else None
                asyncio.run(handlers[('GET','/ltx-resolution/status')](None))
                observation=client.phase_observation(row)['observation']
                self.assertEqual(observation['phase'],phase)
        self.assertFalse((self.run/'resolution-client-phase.json.next').exists())

    def test_http_action_failure_latches_without_leaving_busy_flag(self):
        handlers=self.routes()
        class Request:
            async def json(self):return {'action':'unknown-action'}
        with patch.object(I,'_CTX',self.r):
            result=asyncio.run(handlers[('POST','/ltx-resolution/action')](Request()))
        self.assertTrue(result['halted']);self.assertFalse(self.r.action_busy)
        self.assertIsNotNone(self.r.authority.failed)
        self.assertTrue((self.run/'resolution-halt.json').is_file())

    def test_preview_queue_is_not_hidden_by_idle_pipeline(self):
        self.state.update(preview_pending=1,preview_failures=0)
        with self.assertRaisesRegex(RuntimeError,'Preview work'):self.r.quiescent()
        self.state.update(preview_pending=0,preview_failures=1)
        with self.assertRaisesRegex(RuntimeError,'Preview work'):self.r.quiescent()

    def test_optimized_memory_action_uses_actual_owner_and_fresh_four_card_reads(self):
        adapter_module=load('integration_native_adapter_api','native_adapter.py')
        rows={role:[{'role':role}] for role in SAFETY.ROLES}
        self.r.adapter=types.SimpleNamespace(controller=types.SimpleNamespace(
            expected_residence={role:adapter_module.fingerprint(value) for role,value in rows.items()}),
            _rows=lambda role,require_loaded:rows[role])
        self.r.authority.phase='optimized_preparation'
        self.r.authority.completed.append(self.setup_row('pin0')['name'])
        free=[6,6,2,7];seen=[]
        xpu=types.SimpleNamespace(synchronize=lambda i:seen.append(('sync',i)),
            mem_get_info=lambda i:(free[i]*2**30,32*2**30))
        with patch.dict('sys.modules',{'torch':types.SimpleNamespace(xpu=xpu),'native_adapter':adapter_module}):
            self.r.action('admit-capture0')
        self.assertEqual(seen,[('sync',i) for i in range(4)])
        self.assertIn('admit-capture0',self.r.actions_done)
        evidence=json.loads((self.run/'resolution-admit-capture0.json').read_text())
        self.assertTrue(evidence['allowances_are_not_proven_peak_bounds'])
        self.assertEqual(evidence['physical_free_bytes'],{'xpu:%d'%i:v*2**30 for i,v in enumerate(free)})

    def test_second_capture_requires_first_retirement_and_seven_gib_sampler_floor(self):
        self.r.authority.phase='optimized_preparation'
        self.r.authority.completed.append(self.setup_row('pin1')['name'])
        with self.assertRaisesRegex(RuntimeError,'tails must be retired'):
            self.r.action('admit-capture1')
        self.r.actions_done.add('retire-capture0-tails')
        adapter_module=load('integration_memory_adapter','native_adapter.py')
        rows={role:[{'role':role}] for role in SAFETY.ROLES}
        self.r.adapter=types.SimpleNamespace(controller=types.SimpleNamespace(
            expected_residence={role:adapter_module.fingerprint(value) for role,value in rows.items()}),
            _rows=lambda role,require_loaded:rows[role])
        torch,seen=self.torch_stub((6,7,2,7))
        with patch.dict('sys.modules',{'torch':torch,'native_adapter':adapter_module}):
            with self.assertRaisesRegex(RuntimeError,'memory admission refused'):
                self.r.action('admit-capture1')
        self.assertEqual(seen,list(range(4)))
        receipt=json.loads((self.run/'resolution-admit-capture1.json').read_text())
        self.assertEqual(receipt['required_bytes']['xpu:0'],7*2**30)
        self.assertEqual(receipt['required_bytes']['xpu:1'],7*2**30)
        self.assertNotIn('admit-capture1',self.r.actions_done)

    def test_second_capture_exact_seven_gib_threshold_is_admitted(self):
        self.r.authority.phase='optimized_preparation'
        self.r.authority.completed.append(self.setup_row('pin1')['name'])
        self.r.actions_done.add('retire-capture0-tails')
        adapter_module=load('integration_memory_adapter_at_floor','native_adapter.py')
        rows={role:[{'role':role}] for role in SAFETY.ROLES}
        self.r.adapter=types.SimpleNamespace(controller=types.SimpleNamespace(
            expected_residence={role:adapter_module.fingerprint(value) for role,value in rows.items()}),
            _rows=lambda role,require_loaded:rows[role])
        torch,seen=self.torch_stub((7,7,2,7))
        with patch.dict('sys.modules',{'torch':torch,'native_adapter':adapter_module}):
            self.r.action('admit-capture1')
        self.assertEqual(seen,list(range(4)))
        self.assertIn('admit-capture1',self.r.actions_done)

    def test_decode_admission_requires_both_retirement_actions(self):
        self.r.authority.phase='optimized_preparation'
        self.r.authority.completed.append(self.setup_row('coverage')['name'])
        self.r.actions_done.add('retire-capture0-tails')
        with self.assertRaisesRegex(RuntimeError,'tails must be retired'):
            self.r.action('admit-decode')

    def test_memory_admission_cannot_precede_its_setup_dependency(self):
        self.r.authority.phase='optimized_preparation'
        # A poison CPU stub ensures a missing guard can never touch real Torch.
        def forbidden(*args):raise AssertionError('Device API reached before setup dependency')
        with patch.dict('sys.modules',{'torch':types.SimpleNamespace(xpu=types.SimpleNamespace(synchronize=forbidden))}):
            with self.assertRaisesRegex(RuntimeError,'(?i)(pin|setup|dependency|incomplete)'):
                self.r.action('admit-capture0')
            with self.assertRaisesRegex(RuntimeError,'(?i)(coverage|setup|dependency|incomplete)'):
                self.r.action('admit-decode')
        self.assertFalse((self.run/'resolution-admit-capture0.json').exists())

    def test_twenty_native_barrier_requires_last_fixture_and_binds_all_requests(self):
        self.adapter();self.r.authority.completed.append(self.setup_row('prepare-native')['name'])
        self.r.action('before-native')
        native=[r for r in self.rows if r['phase'] in ('native-reference','native-repeat')]
        self.assertEqual(len(native),20)
        self.assertEqual(native[-1]['fixture'],'wheel')
        self.assertEqual(native[-1]['phase'],'native-repeat')
        self.r.authority.completed.extend(r['name'] for r in native[:-1])
        with self.assertRaisesRegex(RuntimeError,'Twenty native requests'):
            self.r.action('verify-native')
        self.assertFalse((self.run/'native-after.json').exists())
        self.r.authority.completed.append(native[-1]['name'])
        (self.run/'native-preparation.json').write_text('{}')
        observed=[]
        def verifier(root,plan,contract_path,contract_sha,output):
            contract=json.loads(contract_path.read_text());observed.append(contract)
            self.assertEqual(contract['request_names'],[r['name'] for r in native])
            self.assertEqual(contract_sha,self.session.digest(contract_path.read_bytes()))
            # Stop at the boundary; CPU fixtures do not contain generated tensors.
            raise RuntimeError('twenty-request verifier reached')
        with patch.object(REF,'verify_references',side_effect=verifier):
            with self.assertRaisesRegex(RuntimeError,'twenty-request verifier reached'):
                self.r.action('verify-native')
        self.assertEqual(len(observed),1)
        self.assertNotIn('verify-native',self.r.actions_done)
        self.assertEqual(self.r.authority.phase,'native_reference')

    def test_storage_allows_five_gib_drawdown_and_rejects_more(self):
        self.r.previous_free=64*2**30;self.r.consumed=0
        with patch.object(I.shutil,'disk_usage',return_value=types.SimpleNamespace(free=59*2**30)):
            self.r.storage_check()
        self.assertEqual(self.r.consumed,5*2**30)
        with patch.object(I.shutil,'disk_usage',return_value=types.SimpleNamespace(free=59*2**30-1)):
            with self.assertRaisesRegex(RuntimeError,'storage allowance'):self.r.storage_check()

    def test_storage_fresh_admission_reserves_five_gib_above_fifty(self):
        self.r.previous_free=55*2**30;self.r.consumed=0
        with patch.object(I.shutil,'disk_usage',return_value=types.SimpleNamespace(free=55*2**30)):
            self.r.storage_check()
        self.r.previous_free=55*2**30-1;self.r.consumed=0
        with patch.object(I.shutil,'disk_usage',return_value=types.SimpleNamespace(free=55*2**30-1)):
            with self.assertRaisesRegex(RuntimeError,'storage allowance'):self.r.storage_check()

    def test_control_requests_require_fast_proof_and_durable_barrier(self):
        fast=next(r for r in self.rows if r['phase']=='timed')
        deps=self.r.schedule['boundary_dependencies'][fast['name']]
        self.r.authority.completed.extend(d for d in deps if not d.startswith('barrier:'))
        with self.assertRaisesRegex(RuntimeError,'barrier missing'):
            self.r.before_request(fast,'cpu')
        self.r.write('resolution-phase-fast_verified.json',{'synthetic':True})
        with self.assertRaisesRegex(RuntimeError,'Fast proof not verified'):
            self.r.before_request(fast,'cpu')
        self.r.actions_done.add('verify-fast-timed')
        self.r.authority.completed.append(self.setup_row('freeze')['name'])
        self.state.update(captures_frozen=True,loads_frozen=True)
        self.r.before_request(fast,'cpu')

    def test_fast_verification_failure_never_opens_control_barrier(self):
        with patch.object(self.r,'retire_tails'),patch.object(CAND,'verify_outputs',side_effect=RuntimeError('synthetic parity refusal')):
            with self.assertRaisesRegex(RuntimeError,'parity refusal'):
                self.r.action('verify-fast-timed')
        self.assertNotIn('verify-fast-timed',self.r.actions_done)
        self.assertFalse((self.run/'resolution-phase-fast_verified.json').exists())
        with self.assertRaisesRegex(RuntimeError,'Fast proof not verified'):
            self.r.action('verify-timed')

    def test_phase_actions_need_actual_native_completion(self):
        with self.assertRaisesRegex(RuntimeError,'Twenty native requests'):self.r.action('verify-native')
        with self.assertRaisesRegex(RuntimeError,'not verified'):self.r.action('start-optimized')
        self.assertFalse((self.run/'native-runtime-contract.json').exists())


if __name__=='__main__':unittest.main(verbosity=2)
