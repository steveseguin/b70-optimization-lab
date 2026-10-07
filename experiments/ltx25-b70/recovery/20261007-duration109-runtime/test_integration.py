"""CPU integration controls against real authority/schedule/gates; no live runtime imports."""
import asyncio
import copy
import importlib.util
import json
import math
from pathlib import Path
import tempfile
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
        self.duration=load('duration_guard_for_integration','duration_guard.py')
        self.modules=patch.dict('sys.modules',{'ltx_resolution_session':self.session,'schedule':SCHEDULE,
            'runtime_observer':observer,'reference_gate':REF,'candidate_gate':CAND,'setup_gates':GATES,'native_safety':SAFETY,
            'ltx_duration_guard':self.duration,'torch':types.SimpleNamespace()})
        self.modules.start();self.addCleanup(self.modules.stop)
        self.disk=patch.object(I.shutil,'disk_usage',return_value=types.SimpleNamespace(free=64*2**30))
        self.disk.start();self.addCleanup(self.disk.stop)
        self.manifest=json.loads(SCHEDULE.read(SCHEDULE.PARENT/'manifest.json'))
        self.manifest['resolution101']={'parent_manifest_sha256':SCHEDULE.PARENT_SHA}
        self.manifest['files']['source/scripts/ltx_duration_guard.py']=self.session.digest(Path(self.duration.__file__).read_bytes())
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
        self.assertEqual(len(self.r.authority.requests),29)
        self.assertEqual(self.r.authority.phase,'native_reference')
        self.assertEqual(self.r.schedule['raw_capture_requests'],22)
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
        self.first_native_files()
        with patch.object(REF,'tensor_inventory',side_effect=self.inventory_boundary):
            self.r.action('verify-first-native')
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
              'model_verification_sha256':GATES.MODEL_SHA,'output_size':'640x384','frame_count':49,
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

    def test_native_setup_preload_refusal_preserves_evidence_without_controller_or_queries(self):
        admission = {'event': 'preload-admission',
                     'free': {'xpu:0': 8*2**30, 'xpu:1': 7*2**30},
                     'missing_tensor_bytes': {'xpu:0': 1024, 'xpu:1': 2048},
                     'required': {'xpu:0': 8*2**30+1127, 'xpu:1': 8*2**30+2253},
                     'state': {'sampler_routes': 0}}
        reason = 'Insufficient space before native full residency'
        class Adapter:
            def __init__(self, **kwargs):
                self.controller = None
                self.receipts = []
            def prepare(this):
                this.receipts.extend([copy.deepcopy(admission), {'event':'adapter-failure','reason':reason}])
                raise RuntimeError(reason)
            def abort_request(this, error):
                raise AssertionError('Uninitialized controller cleanup must not run')
            def _inspect(this, *args):
                raise AssertionError('No fresh device inspection during failure handling')
        row = self.setup_row('prepare-native')
        self.r.authority.completed.append(self.setup_row('window-probe')['name'])
        runtime = self.r
        class Executor:
            def __init__(self):self.server=types.SimpleNamespace(client_id=None)
            def add_message(self,event,data,broadcast):self.status_messages.append((event,data))
            async def execute_async(this,prompt,pid,extra,outputs):
                this.add_message('execution_start', {'prompt_id':pid}, False)
                runtime.prepare_native(row['name'])
        GUARD.install(Executor,self.r.authority,self.r.before_request,self.r.after_request,self.r.on_failure)
        mm=types.ModuleType('comfy.model_management');comfy=types.ModuleType('comfy');comfy.model_management=mm
        # The fake torch has no device API; receipt serialization uses already
        # collected rows only. Real executor dispatch must latch the failure.
        with patch.dict('sys.modules', {'torch':types.ModuleType('torch'),'nodes':types.ModuleType('nodes'),
                'comfy':comfy,'comfy.model_management':mm,'native_adapter':types.SimpleNamespace(NativeAdapter=Adapter)}):
            executor=Executor()
            asyncio.run(executor.execute_async(row['graph'],'cpu-prepare-refused'))
        self.assertFalse(executor.success)
        self.assertNotIn(row['name'],self.r.authority.completed)
        self.assertTrue((self.run/'resolution-halt.json').is_file())
        self.assertFalse((self.run/'native-preparation.json').exists())
        receipt=json.loads((self.run/('native-failure-'+row['name']+'.json')).read_text())
        self.assertEqual(receipt['adapter_receipts'],[admission,{'event':'adapter-failure','reason':reason}])
        self.assertEqual(receipt['controller_receipts'],[])
        self.assertFalse(receipt['controller_initialized'])
        self.assertTrue(receipt['adapter_initialized'])
        self.assertEqual(receipt['error'],reason)
        self.assertEqual(receipt['prompt_id'],'cpu-prepare-refused')
        self.assertEqual(receipt['phase'],'native-setup')
        self.assertEqual(receipt['plan_sha256'],self.session.PLAN_SHA256)
        self.assertEqual(receipt['runtime_manifest_sha256'],'a'*64)
        self.assertEqual(receipt['server_identity_sha256'],self.r.identity_sha)
        errors=[data for event,data in executor.status_messages if event=='execution_error']
        self.assertEqual(len(errors),1)
        self.assertIsNone(errors[0]['failure_cleanup_error'])

    def test_native_setup_failure_before_adapter_exists_is_durable_and_exclusive(self):
        row=self.setup_row('prepare-native')
        fsync=self.session.os.fsync
        with patch.object(self.session.os,'fsync',wraps=fsync) as synced:
            self.r.on_failure(row,'cpu-constructor-refused',RuntimeError('source identity refused'))
        self.assertEqual(synced.call_count,2)  # file and containing directory
        path=self.run/('native-failure-'+row['name']+'.json')
        original=path.read_bytes();receipt=json.loads(original)
        self.assertFalse(receipt['adapter_initialized'])
        self.assertFalse(receipt['controller_initialized'])
        self.assertEqual(receipt['adapter_receipts'],[])
        self.assertEqual(receipt['controller_receipts'],[])
        with self.assertRaises(FileExistsError):
            self.r.on_failure(row,'cpu-retry-not-allowed',RuntimeError('later refusal'))
        self.assertEqual(path.read_bytes(),original)

    def test_native_setup_initialized_controller_abort_still_preserves_receipts(self):
        adapter,seen=self.adapter();row=self.setup_row('prepare-native')
        def abort(error):
            seen.append(('abort',str(error)))
            adapter.controller.receipts.append({'event':'latched','reason':str(error)})
            raise RuntimeError('controller permanently latched')
        adapter.abort_request=abort
        with self.assertRaisesRegex(RuntimeError,'permanently latched'):
            self.r.on_failure(row,'cpu-postload-refused',RuntimeError('postload memory refused'))
        receipt=json.loads((self.run/('native-failure-'+row['name']+'.json')).read_text())
        self.assertTrue(receipt['controller_initialized'])
        self.assertEqual(receipt['controller_receipts'],[{'event':'latched','reason':'postload memory refused'}])
        self.assertEqual(seen,[('abort','postload memory refused')])

    def test_failure_receipt_does_not_expand_to_optimized_phases(self):
        adapter,seen=self.adapter()
        row=next(row for row in self.rows if row['phase']=='candidate-check')
        self.r.on_failure(row,'cpu-candidate',RuntimeError('candidate refused'))
        self.assertEqual(seen,[])
        self.assertFalse((self.run/('native-failure-'+row['name']+'.json')).exists())

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
        row=self.rows[6];self.r.authority.completed.append(self.setup_row('freeze')['name'])
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
                              ('optimized_preparation',self.setup_row('pin0')),('timing',self.rows[13])]:
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
        free=[7,7,2,9];seen=[]
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
        torch,seen=self.torch_stub((6,7,2,9))
        with patch.dict('sys.modules',{'torch':torch,'native_adapter':adapter_module}):
            with self.assertRaisesRegex(RuntimeError,'memory admission refused'):
                self.r.action('admit-capture1')
        self.assertEqual(seen,list(range(4)))
        receipt=json.loads((self.run/'resolution-admit-capture1.json').read_text())
        self.assertEqual(receipt['required_bytes']['xpu:0'],7*2**30)
        self.assertEqual(receipt['required_bytes']['xpu:1'],7*2**30)
        self.assertNotIn('admit-capture1',self.r.actions_done)

    def test_second_capture_exact_49frame_thresholds_are_admitted(self):
        self.r.authority.phase='optimized_preparation'
        self.r.authority.completed.append(self.setup_row('pin1')['name'])
        self.r.actions_done.add('retire-capture0-tails')
        adapter_module=load('integration_memory_adapter_at_floor','native_adapter.py')
        rows={role:[{'role':role}] for role in SAFETY.ROLES}
        self.r.adapter=types.SimpleNamespace(controller=types.SimpleNamespace(
            expected_residence={role:adapter_module.fingerprint(value) for role,value in rows.items()}),
            _rows=lambda role,require_loaded:rows[role])
        torch,seen=self.torch_stub((7,7,2,9))
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

    def test_six_native_barrier_requires_last_fixture_and_binds_all_requests(self):
        self.adapter();self.r.authority.completed.append(self.setup_row('prepare-native')['name'])
        self.r.action('before-native')
        native=[r for r in self.rows if r['phase'] in ('native-reference','native-repeat')]
        self.assertEqual(len(native),6)
        self.assertEqual(native[-1]['fixture'],'bird')
        self.assertEqual(native[-1]['phase'],'native-repeat')
        self.r.authority.completed.extend(r['name'] for r in native[:-1])
        with self.assertRaisesRegex(RuntimeError,'Six native requests'):
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
            raise RuntimeError('six-request verifier reached')
        with patch.object(self.r,'capture_checkpoint') as checkpoint,patch.object(REF,'verify_references',side_effect=verifier):
            with self.assertRaisesRegex(RuntimeError,'six-request verifier reached'):
                self.r.action('verify-native')
        checkpoint.assert_called_once_with('native',6)
        self.assertEqual(len(observed),1)
        self.assertNotIn('verify-native',self.r.actions_done)
        self.assertEqual(self.r.authority.phase,'native_reference')

    def test_storage_allows_four_gib_drawdown_and_rejects_more(self):
        self.r.previous_free=64*2**30;self.r.consumed=0
        with patch.object(I.shutil,'disk_usage',return_value=types.SimpleNamespace(free=60*2**30)):
            self.r.storage_check()
        self.assertEqual(self.r.consumed,4*2**30)
        with patch.object(I.shutil,'disk_usage',return_value=types.SimpleNamespace(free=60*2**30-1)):
            with self.assertRaisesRegex(RuntimeError,'storage allowance'):self.r.storage_check()

    def test_storage_fresh_admission_reserves_four_gib_above_fifty(self):
        self.r.previous_free=54*2**30;self.r.consumed=0
        with patch.object(I.shutil,'disk_usage',return_value=types.SimpleNamespace(free=54*2**30)):
            self.r.storage_check()
        self.r.previous_free=54*2**30-1;self.r.consumed=0
        with patch.object(I.shutil,'disk_usage',return_value=types.SimpleNamespace(free=54*2**30-1)):
            with self.assertRaisesRegex(RuntimeError,'storage allowance'):self.r.storage_check()

    def test_control_request_and_action_are_not_admitted(self):
        row = dict(self.rows[-1], phase='timed')
        with self.assertRaisesRegex(RuntimeError, 'Control requests'):
            self.r.before_request(row, 'cpu')
        with patch.object(self.r, 'retire_tails') as retire:
            with self.assertRaisesRegex(RuntimeError, 'Unknown finite'):
                self.r.action('verify-timed')
        retire.assert_not_called()

    def test_fast_verification_failure_never_writes_completion_barrier(self):
        with patch.object(self.r,'retire_tails'),patch.object(self.r,'capture_checkpoint') as checkpoint,patch.object(CAND,'verify_outputs',side_effect=RuntimeError('synthetic parity refusal')):
            with self.assertRaisesRegex(RuntimeError,'parity refusal'):
                self.r.action('verify-fast-timed')
        checkpoint.assert_called_once_with('timed-fast',22)
        self.assertNotIn('verify-fast-timed',self.r.actions_done)
        self.assertFalse((self.run/'resolution-phase-fast_verified.json').exists())
        with self.assertRaisesRegex(RuntimeError,'Unknown finite'):
            self.r.action('verify-timed')

    def test_phase_actions_need_actual_native_completion(self):
        with self.assertRaisesRegex(RuntimeError,'Six native requests'):self.r.action('verify-native')
        with self.assertRaisesRegex(RuntimeError,'not verified'):self.r.action('start-optimized')
        self.assertFalse((self.run/'native-runtime-contract.json').exists())

    def first_native_files(self):
        """Real paths/JSON/SHA, tiny archive fixture at explicit parser boundary."""
        first=self.rows[0]
        if self.r.adapter is None:self.adapter()
        self.r.actions_done.add('before-native')
        for name in (self.setup_row('prepare-native')['name'],first['name']):
            if name not in self.r.authority.completed:self.r.authority.completed.append(name)
        self.archive_bytes=b'CPU integration boundary: no generated tensor payload'
        self.first_folder=self.root/'output/validation'/first['name']
        self.first_folder.mkdir(parents=True,exist_ok=True)
        shapes={'images':[49,384,640,3],'video_latent':[1,128,7,12,20],
                'audio_latent':[1,8,51,16],'waveform':[1,2,96480]}
        self.assertEqual(REF.SHAPES,shapes)
        self.first_metadata={'run_name':first['name'],'sample_rate':48000,
            'deterministic_enabled':True,'deterministic_warn_only':False,
            'tensors':{k:{'shape':v,'dtype':'torch.float32','sha256':'e'*64,'finite':True}
                       for k,v in shapes.items()}}
        self.first_memory={'event':'after','request_id':first['name'],'admitted':True,
            'snapshot':{'plan_sha256':self.session.PLAN_SHA256,'runtime_sha256':'a'*64,
                'phase':'native-reference','fault':False,
                'physical_free_bytes':{'xpu:%d'%i:2*2**30 for i in range(4)}}}
        self.first_memory_path=self.run/('native-memory-after-'+first['name']+'.json')
        self.write_first_native_files()

    def write_first_native_files(self):
        (self.first_folder/'summary.json').write_text(json.dumps(self.first_metadata))
        (self.first_folder/'tensors.safetensors').write_bytes(self.archive_bytes)
        self.first_memory_path.write_text(json.dumps(self.first_memory))

    def inventory_boundary(self,raw,metadata):
        # Parsing146MB of F32 data is reference_gate's separately tested job.
        # This boundary asserts integration forwards exact actual-file bytes and
        # unchanged49-frame metadata; no model/tensor runtime is imported.
        self.assertEqual(raw,self.archive_bytes)
        self.assertEqual(metadata,self.first_metadata['tensors'])
        for key,shape in REF.SHAPES.items():
            REF.require(metadata[key]['shape']==shape,'Synthetic archive shape refusal')
            REF.require(metadata[key]['dtype']=='torch.float32' and metadata[key]['finite'] is True,
                        'Synthetic archive finite/dtype refusal')
        return copy.deepcopy(metadata)

    def assert_second_native_blocked(self):
        with patch.object(self.r.adapter,'before_request',side_effect=AssertionError('Native work reached')):
            with self.assertRaisesRegex(RuntimeError,'(?i)(barrier|admission|evidence)'):
                self.r.before_request(self.rows[1],'cpu-second')

    def test_first_native_barrier_binds_actual_files_and_allows_only_next_native(self):
        self.first_native_files()
        self.assert_second_native_blocked()
        with patch.object(REF,'tensor_inventory',side_effect=self.inventory_boundary) as parser:
            self.r.action('verify-first-native')
        parser.assert_called_once()
        barrier=self.run/'resolution-phase-first_native_verified.json'
        receipt=json.loads(barrier.read_text())
        self.assertEqual(receipt['frame_count'],49)
        self.assertEqual(receipt['name'],self.rows[0]['name'])
        self.assertEqual(receipt['plan_sha256'],self.session.PLAN_SHA256)
        self.assertEqual(receipt['runtime_manifest_sha256'],'a'*64)
        self.assertEqual(receipt['server_identity_sha256'],self.r.identity_sha)
        self.assertEqual(receipt['archive_sha256'],REF.sha(self.archive_bytes))
        self.assertEqual(receipt['metadata_sha256'],REF.sha((self.first_folder/'summary.json').read_bytes()))
        self.assertEqual(receipt['memory_after_sha256'],REF.sha(self.first_memory_path.read_bytes()))
        self.assertEqual(receipt['tensors']['audio_latent']['shape'],[1,8,51,16])
        self.assertEqual(self.r.authority.phase,'native_reference')
        self.assertIsNone(self.r.authority.references_sha)
        with patch.object(self.r.adapter,'before_request',return_value={'admitted':True}) as before:
            self.r.before_request(self.rows[1],'cpu-second')
        before.assert_called_once_with(self.rows[1]['name'])
        self.assertNotIn('verify-native',self.r.actions_done)
        with self.assertRaisesRegex(RuntimeError,'not verified'):self.r.action('start-optimized')

    def test_first_native_barrier_must_follow_first_and_precede_all_other_natives(self):
        self.adapter();self.r.actions_done.add('before-native')
        with patch.object(REF,'tensor_inventory',side_effect=AssertionError('premature parser reached')):
            with self.assertRaisesRegex(RuntimeError,'precede'):self.r.action('verify-first-native')
            self.r.authority.completed.extend([self.rows[0]['name'],self.rows[1]['name']])
            with self.assertRaisesRegex(RuntimeError,'precede'):self.r.action('verify-first-native')
        self.assertFalse((self.run/'native-first.json').exists())
        self.assertNotIn('verify-first-native',self.r.actions_done)

    def test_fabricated_barrier_file_without_verified_action_cannot_admit_second(self):
        self.first_native_files()
        (self.run/'resolution-phase-first_native_verified.json').write_text('{}')
        self.assert_second_native_blocked()

    def test_first_native_shape_audio_or_nonfinite_rejection_blocks_second(self):
        for mode in ('image-shape','audio-length','waveform-length','nonfinite','wrong-dtype'):
            with self.subTest(mode=mode):
                self.setUp();self.first_native_files()
                items=self.first_metadata['tensors']
                if mode=='image-shape':items['images']['shape']=[25,384,640,3]
                if mode=='audio-length':items['audio_latent']['shape']=[1,8,26,16]
                if mode=='waveform-length':items['waveform']['shape']=[1,2,48480]
                if mode=='nonfinite':items['images']['finite']=False
                if mode=='wrong-dtype':items['video_latent']['dtype']='torch.bfloat16'
                self.write_first_native_files()
                with patch.object(REF,'tensor_inventory',side_effect=self.inventory_boundary):
                    with self.assertRaisesRegex(ValueError,'Synthetic archive'):self.r.action('verify-first-native')
                self.assertNotIn('verify-first-native',self.r.actions_done)
                self.assertFalse((self.run/'resolution-phase-first_native_verified.json').exists())
                self.assert_second_native_blocked()

    def test_first_native_capture_metadata_identity_refused_before_parser(self):
        for key,value in [('run_name','another-request'),('sample_rate',16000),
                          ('deterministic_enabled',False),('deterministic_warn_only',True)]:
            with self.subTest(key=key):
                self.setUp();self.first_native_files();self.first_metadata[key]=value
                self.write_first_native_files()
                with patch.object(REF,'tensor_inventory',side_effect=AssertionError('unbound parser reached')):
                    with self.assertRaisesRegex(RuntimeError,'capture identity'):self.r.action('verify-first-native')
                self.assert_second_native_blocked()

    def test_first_native_memory_floor_and_identity_cannot_be_forged(self):
        for mode in ('floor','missing-card','float-bytes','bool-bytes','request','plan','runtime','phase','fault','event','not-admitted'):
            with self.subTest(mode=mode):
                self.setUp();self.first_native_files()
                snap=self.first_memory['snapshot']
                if mode=='floor':snap['physical_free_bytes']['xpu:3']=2*2**30-1
                if mode=='missing-card':del snap['physical_free_bytes']['xpu:2']
                if mode=='float-bytes':snap['physical_free_bytes']['xpu:0']=float(2*2**30)
                if mode=='bool-bytes':snap['physical_free_bytes']['xpu:0']=True
                if mode=='request':self.first_memory['request_id']='another-request'
                if mode=='plan':snap['plan_sha256']='f'*64
                if mode=='runtime':snap['runtime_sha256']='f'*64
                if mode=='phase':snap['phase']='timing'
                if mode=='fault':snap['fault']=True
                if mode=='event':self.first_memory['event']='before'
                if mode=='not-admitted':self.first_memory['admitted']=False
                self.write_first_native_files()
                with patch.object(REF,'tensor_inventory',side_effect=self.inventory_boundary):
                    with self.assertRaisesRegex(RuntimeError,'memory floor'):self.r.action('verify-first-native')
                self.assertNotIn('verify-first-native',self.r.actions_done)
                self.assert_second_native_blocked()

    def test_admitted_first_native_files_cannot_change_before_second(self):
        for filename in ('archive','metadata','memory','barrier'):
            with self.subTest(filename=filename):
                self.setUp();self.first_native_files()
                with patch.object(REF,'tensor_inventory',side_effect=self.inventory_boundary):
                    self.r.action('verify-first-native')
                path={'archive':self.first_folder/'tensors.safetensors','metadata':self.first_folder/'summary.json',
                      'memory':self.first_memory_path,'barrier':self.run/'resolution-phase-first_native_verified.json'}[filename]
                path.write_bytes(path.read_bytes()+b' ')
                self.assert_second_native_blocked()

    def capture_tensors(self,shapes):
        class Tensor:
            dtype='torch.float32';device='cpu';layout='torch.strided'
            def __init__(self,shape):self.shape=shape
            def numel(self):return math.prod(self.shape)
            def element_size(self):return 4
            def is_contiguous(self):return True
        return {key:Tensor(shape) for key,shape in shapes.items()}

    def capture_report(self,tensors,name):
        return {'run_name':name,'sample_rate':48000,
                'tensors':{key:{'shape':list(t.shape),'dtype':'torch.float32','finite':True,
                              'sha256':'e'*64,'min':0.,'max':1.,'std':.1} for key,t in tensors.items()}}

    def reserve_capture_prefix(self,count):
        order=self.rows[:6]+[self.setup_row('capture0'),self.setup_row('capture1')]+self.rows[6:]
        self.assertEqual(len(order),22)
        self.assertEqual([row['name'] for row in self.r.capture_guard.rows],[row['name'] for row in order])
        for i in range(self.r.capture_guard.receipt()['captures_reserved'],count):
            row=order[i]
            with self.r.authority.lock:
                self.r.authority.active={'name':row['name'],'prompt_id':'cpu-capture-%d'%i,'start_ns':i}
            binding=self.r.active_capture_request()
            self.assertEqual(binding,{'name':row['name'],'prompt_id':'cpu-capture-%d'%i,
                'plan_sha256':self.session.PLAN_SHA256,'graph_sha256':row['graph_sha256']})
            role=self.r.capture_guard.rows[i]['role']
            shapes=self.duration.FULL_SHAPES if role=='full' else self.duration.FILL_SHAPES
            ts=self.capture_tensors(shapes)
            evidence=self.r.capture_guard.validate(ts,self.capture_report(ts,row['name']),row['name'])
            self.assertEqual(evidence['role'],role)
            self.r.authority.completed.append(row['name'])
            self.r.authority.active=None

    def test_real_capture_guard_follows_execution_order_including_setup_before_candidates(self):
        self.reserve_capture_prefix(22)
        self.assertEqual(self.r.capture_guard.receipt()['captures_reserved'],22)
        self.assertEqual(self.r.capture_guard.receipt()['reserved_bytes'],self.duration.RAW_CAPTURE_BUDGET)

    def test_capture_checkpoints_persist_real_guard_reservations_at_six_fifteen_twenty_two(self):
        for label,count in [('native',6),('candidate',15),('timed-fast',22)]:
            self.reserve_capture_prefix(count)
            self.r.capture_checkpoint(label,count)
            path=self.run/('duration-capture-'+label+'.json')
            value=json.loads(path.read_text())
            self.assertEqual(value['runtime_manifest_sha256'],'a'*64)
            self.assertEqual(value['server_identity_sha256'],self.r.identity_sha)
            self.assertEqual(value['prewrite'],self.r.capture_guard.receipt())
            self.assertEqual(value['prewrite']['captures_reserved'],count)
            self.assertEqual(value['prewrite']['plan_sha256'],self.session.PLAN_SHA256)
            self.assertEqual(value['prewrite']['reserved_bytes'],sum(r['charged_bytes'] for r in value['prewrite']['captures']))
        # Earlier phase evidence remains its original immutable snapshot.
        native=json.loads((self.run/'duration-capture-native.json').read_text())
        self.assertEqual(native['prewrite']['captures_reserved'],6)
        self.assertEqual(len(native['prewrite']['captures']),6)

    def test_short_capture_checkpoint_refuses_before_file_write(self):
        self.reserve_capture_prefix(5)
        with self.assertRaisesRegex(RuntimeError,'reservation evidence differs'):
            self.r.capture_checkpoint('native',6)
        self.assertFalse((self.run/'duration-capture-native.json').exists())

    def test_mutated_capture_checkpoint_evidence_refuses_before_file_write(self):
        for change in ('failed','plan','count','cap','order','reserved_bytes','charge','budget','completion'):
            with self.subTest(change=change):
                self.setUp();self.reserve_capture_prefix(6)
                value=self.r.capture_guard.receipt()
                if change=='failed':value['failed']='synthetic failure'
                if change=='plan':value['plan_sha256']='f'*64
                if change=='count':value['captures_reserved']=5
                if change=='cap':value['capture_cap']=23
                if change=='order':value['captures'].reverse()
                if change=='reserved_bytes':value['reserved_bytes']+=1
                if change=='charge':value['captures'][0]['charged_bytes']+=1
                if change=='budget':value['raw_budget_bytes']=value['reserved_bytes']-1
                if change=='completion':self.r.authority.completed.remove(value['captures'][-1]['name'])
                with patch.object(self.r.capture_guard,'receipt',return_value=value):
                    with self.assertRaisesRegex(RuntimeError,'reservation evidence differs'):
                        self.r.capture_checkpoint('native',6)
                self.assertFalse((self.run/'duration-capture-native.json').exists())

    def test_candidate_action_keeps_capture_checkpoint_and_parity_gate_independent(self):
        self.reserve_capture_prefix(15)
        with patch.object(self.r,'retire_tails'),patch.object(CAND,'verify_outputs',side_effect=RuntimeError('candidate parity refusal')):
            with self.assertRaisesRegex(RuntimeError,'candidate parity refusal'):
                self.r.action('verify-candidate')
        self.assertTrue((self.run/'duration-capture-candidate.json').exists())
        self.assertNotIn('verify-candidate',self.r.actions_done)
        self.assertFalse((self.run/'resolution-phase-candidate_verified.json').exists())
        self.assertIsNone(self.r.authority.candidate_sha)

    def test_capture_callback_uses_registered_graph_not_untrusted_active_fields(self):
        row=self.rows[0]
        self.r.authority.begin(row['name'],row['graph'],'trusted-cpu-prompt')
        self.r.authority.active['graph_sha256']='f'*64
        self.r.authority.active['plan_sha256']='f'*64
        self.r.authority.active['role']='fill'
        value=self.r.active_capture_request()
        self.assertEqual(value['graph_sha256'],row['graph_sha256'])
        self.assertEqual(value['plan_sha256'],self.session.PLAN_SHA256)
        self.assertEqual(value['prompt_id'],'trusted-cpu-prompt')
        self.assertNotIn('role',value)
        ts=self.capture_tensors(self.duration.FULL_SHAPES)
        with self.assertRaisesRegex(RuntimeError,'identity differs'):
            self.r.capture_guard.validate(ts,self.capture_report(ts,'spoofed-name'),'spoofed-name')

    def test_capture_callback_requires_live_healthy_authority(self):
        with self.assertRaisesRegex(RuntimeError,'no active'):self.r.active_capture_request()
        row=self.rows[0];self.r.authority.begin(row['name'],row['graph'],'trusted-cpu-prompt')
        self.r.authority.halt('synthetic fault')
        with self.assertRaises(RuntimeError):self.r.active_capture_request()

    def test_capture_guard_source_identity_checked_before_configuration(self):
        session=load('fresh_guard_identity_session','session.py')
        guard=load('fresh_wrong_duration_guard','duration_guard.py')
        self.manifest['files']['source/scripts/ltx_duration_guard.py']='f'*64
        with patch.dict('sys.modules',{'ltx_resolution_session':session,'ltx_duration_guard':guard}):
            with self.assertRaisesRegex(RuntimeError,'guard source differs'):
                I.Runtime(self.packet,self.manifest,'a'*64,self.run)
        self.assertIsNone(guard._guard)





if __name__=='__main__':unittest.main(verbosity=2)
