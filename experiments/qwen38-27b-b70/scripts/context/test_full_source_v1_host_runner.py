"""CPU-only admission/ownership tests; no process, endpoint or device actions."""
from contextlib import contextmanager, ExitStack
import copy
import io
import json
from pathlib import Path
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import full_source_v1_host_runner as runner

q=runner.qualified


def packet():
    rows=[];tasks={};requests={}
    for index,case in enumerate(runner.ORDER):
        rows.append({'case_id':case,'task_sha256':str(index+1)*64,'request_sha256':str(index+3)*64,
            'question_sha256':str(index+5)*64,'request_path':case+'-request.json','task_path':case+'-task.json',
            'result_path':case+'/result.json','timing_path':case+'/timing.json'})
        tasks[case]={'document_id':case,'task_sha256':rows[-1]['task_sha256'],'batches':[{}]*12,'questions':[{}]*24}
        requests[case]={'model':runner.MODEL}
    return {'plan':{'schema':'full-source-plan.v1','protocol':runner.PROTOCOL,'expected_trials':2,
            'trials':rows,'source_code_sha256':{'client.py':'fixed'},**copy.deepcopy(runner.POLICY)},
            'tasks':tasks,'requests':requests}


def profile():
    return {'rung':{'tp':2,'mem':.95,'max_model_len':262144,'batched':832,'seqs':1,'mtp':5,
        'draft_int4':True,'fa_verify_rows':True,'prefix_cache':'off','warmup':False,'image':q.IMAGE,
        'shortlist':'/fixed/list','overlay':[],'extra_env':[],'env':[],'serve_arg':[]},
        'argv':['docker','run',q.IMAGE,'vllm','serve','--no-enable-prefix-caching'],
        'overlay_sha256':{},'reference_sha256':'ref','guard_sha256':'guard'}


def strict():
    return {'schema':'neural.download.strict-attempt-output-comparison.v1',
        'comparison':{'exact_prompts':12,'total_prompts':12,'complete_token_arrays_exact':True},
        'qualification':{'all_workload_and_canary_gates_passed':True,'strict_pair_qualified':True}}


class PacketTests(unittest.TestCase):
    def test_strict_requires_exact_integer_counts(self):
        self.assertTrue(runner.strict_passed(strict()))
        for key in ('exact_prompts','total_prompts'):
            value=strict();value['comparison'][key]=12.0
            self.assertFalse(runner.strict_passed(value))

    def test_fixed_order_and_policy(self):
        self.assertEqual(len(runner.expected_trials(packet())),2)
        for mode in ('extra','reordered','float','thinking','model','path','task'):
            p=packet()
            if mode=='extra':p['plan']['trials'].append(p['plan']['trials'][0])
            elif mode=='reordered':p['plan']['trials'].reverse()
            elif mode=='float':p['plan']['max_requests_per_trial']=1.0
            elif mode=='thinking':p['plan']['answer_generation']['enable_thinking']=1
            elif mode=='model':p['requests'][runner.ORDER[0]]['model']='other'
            elif mode=='path':p['plan']['trials'][0]['request_path']='../escape'
            else:p['plan']['trials'][0]['task_sha256']='wrong'
            with self.subTest(mode=mode),self.assertRaises(RuntimeError):runner.expected_trials(p)

    def test_validator_is_cpu_only_and_requires_full_receipt(self):
        with patch.object(runner.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps(packet()),stderr='')) as run:
            runner.validate_packet(Path('/fixture'))
            args=run.call_args.args[0]
            self.assertNotIn('--execute',args);self.assertIn('-B',args)
            self.assertEqual(run.call_args.kwargs['env']['HF_HUB_OFFLINE'],'1')
        with patch.object(runner.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout='',stderr='bad')):
            with self.assertRaises(RuntimeError):runner.validate_packet(Path('/fixture'))

    def test_prior_active_short_circuits_before_reading_trials(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);q.atomic(p/'status.json',{'phase':'history-study'})
            with patch.object(q,'run_evidence_audit') as audit,patch.object(q,'validate_study_packet') as validator:
                with self.assertRaisesRegex(RuntimeError,'finish first'):runner.previous_receipts(p)
                audit.assert_not_called();validator.assert_not_called()

    def test_only_path_prefix_fields_can_be_normalized(self):
        v={'output':'/old','child':{'directory':'/old/native','other':'/old/native'},'payload':'/old'}
        changed=runner.normalized(v,Path('/old'))
        self.assertEqual(changed['child']['directory'],'<restored-root>/native')
        self.assertEqual(changed['child']['other'],'/old/native');self.assertEqual(changed['payload'],'/old')


class PreservationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.previous=self.base/'original';self.previous.mkdir()
        self.root=self.base/'saved';self.root.mkdir()
        self.audit={'output':str(self.previous),'trials':[]}
        for case in runner.ORDER:
            for condition in ('AS','AH','QS','QH'):
                name=f'diagnostic/{case}-{condition}/native/canonical.sqlite'
                p=self.previous/name;p.parent.mkdir(parents=True);p.write_bytes((case+condition).encode())
                self.audit['trials'].append({'case_id':case,'condition':condition,'directory':str(p.parent)})
        q.atomic(self.previous/'diagnostic-independent-audit.json',self.audit)
        q.atomic(self.root/'audit.json',self.audit)
        self.archive=self.root/'canonical-stores.tar.gz'
        with tarfile.open(self.archive,'w:gz') as tar:
            for p in sorted(self.previous.rglob('canonical.sqlite')):tar.add(p,arcname=str(p.relative_to(self.previous)))
        self.refresh()

    def refresh(self):
        files={str(p.relative_to(self.root)):q.sha(p) for p in self.root.rglob('*')
               if p.is_file() and p.name not in ('inventory.json','preservation.json')}
        q.atomic(self.root/'inventory.json',{'schema':'history-study-preservation.v1','source_output':str(self.previous),
                 'files_sha256':files,'sqlite_members_verified':8})
        q.atomic(self.root/'preservation.json',{'schema':'context-history-preservation.v1','output':str(self.previous),
            'complete':True,'restored_audit_matches':True,'normalization':['output','directory'],
            'inventory_sha256':q.sha(self.root/'inventory.json'),'archive_path':self.archive.name,
            'archive_sha256':q.sha(self.archive),'audit_path':'audit.json','audit_sha256':q.sha(self.root/'audit.json')})

    def replay(self,script,output,packet):
        value=copy.deepcopy(self.audit)
        value['output']=str(output)
        for row in value['trials']:
            old=row['directory'];row['directory']=str(output)+old[len(str(self.previous)):]
            self.assertTrue((Path(row['directory'])/'canonical.sqlite').is_file())
        return value

    def call(self):
        return runner.preservation_receipt(self.root/'preservation.json',self.previous,self.previous/'diagnostic-independent-audit.json')

    def test_valid_restore_is_reaudited_not_trusted_boolean(self):
        with patch.object(q,'run_evidence_audit',side_effect=self.replay) as audit:
            bindings=self.call();self.assertIn(str(self.archive),bindings);audit.assert_called_once()

    def test_changed_archive_is_refused(self):
        self.archive.write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError,'archive identity'):self.call()

    def test_unsafe_or_incomplete_archive_refused_even_with_rebound_hash(self):
        for name in ('../escape','diagnostic/one.sqlite'):
            with tarfile.open(self.archive,'w:gz') as tar:
                m=tarfile.TarInfo(name);m.size=1;tar.addfile(m,io.BytesIO(b'x'))
            self.refresh()
            with self.assertRaisesRegex(RuntimeError,'exactly eight'):self.call()

    def test_valid_archive_with_changed_database_is_refused(self):
        first=next(self.previous.rglob('canonical.sqlite'));first.write_bytes(b'new')
        with self.assertRaisesRegex(RuntimeError,'SQLite differs'):self.call()

    def test_restored_semantic_change_cannot_be_normalized(self):
        def bad(*args):
            value=self.replay(*args);value['trials'][0]['quality_passed']=True;return value
        with patch.object(q,'run_evidence_audit',side_effect=bad):
            with self.assertRaisesRegex(RuntimeError,'beyond output'):self.call()


class PriorAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.out=Path(self.temp.name);(self.out/'server').mkdir();(self.out/'diagnostic').mkdir()
        self.boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        queue={'schema':'history-study-host-queue.v1','protocol':'context-history-study-live-v1',
            'port':18196,'model':runner.MODEL,'hostname':runner.socket.gethostname(),'boot_id':self.boot,
            'dependency_sha256':{str(Path(q.__file__).resolve()):q.sha(q.__file__),str(q.HEALTH):q.sha(q.HEALTH)}}
        self.audit={'continuation':{'evidence_complete':True,'continuation_signal':False,'extension_admitted':False},
                    'trials':[{'quality_passed':False} for _ in range(8)]}
        records={'status.json':{'phase':'completed','cards_released':True},'queue.json':queue,'server/launch.json':profile(),
            'server-stop.json':{'boot_id':self.boot,'stop_confirmed':True,'owner_pid':123,'container_id':'one','image_id':q.IMAGE},
            'cards-released.json':{'verified':True},'diagnostic-independent-audit.json':self.audit,
            'diagnostic-host-audit.json':{},'postflight-health.command.json':{'argv':['bash',str(q.HEALTH)]},'strict-comparison.json':strict()}
        records['server/state.json']=copy.deepcopy(records['server-stop.json'])
        for name,value in records.items():q.atomic(self.out/name,value)
        (self.out/'lifecycle.jsonl').write_text(json.dumps({'phase':'completed'})+'\n')
        (self.out/'postflight-health.log').write_text('healthy\n')
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(q,'validate_study_packet',return_value={'plan':{'engine_source_sha256':{}}}))
        self.stack.enter_context(patch.object(q,'expected_trials',return_value=[]))
        self.stack.enter_context(patch.object(q,'verify_diagnostic',return_value={}))
        self.stack.enter_context(patch.object(q,'verify_independent_study'))
        self.reaudit=self.stack.enter_context(patch.object(q,'run_evidence_audit',side_effect=lambda *args:runner.read(self.out/'diagnostic-independent-audit.json')))
        self.restore=self.stack.enter_context(patch.object(runner,'preservation_receipt',return_value={'preserved':'hash'}))

    def test_complete_negative_requires_reaudit_and_preservation(self):
        prior,files=runner.previous_receipts(self.out)
        self.assertFalse(prior['full_source_admission']['continuation_signal'])
        self.reaudit.assert_called_once();self.restore.assert_called_once();self.assertIn('preserved',files)

    def test_positive_or_incomplete_history_cannot_be_replaced(self):
        for field,value in [('continuation_signal',True),('continuation_signal',None),('evidence_complete',False)]:
            audit=copy.deepcopy(self.audit);audit['continuation'][field]=value
            q.atomic(self.out/'diagnostic-independent-audit.json',audit)
            with self.subTest(field=field,value=value),self.assertRaisesRegex(RuntimeError,'continuation has priority'):
                runner.previous_receipts(self.out)
        self.restore.assert_not_called()

    def test_reboot_or_missing_release_refused(self):
        for mode in ('boot','stop','cards'):
            if mode=='boot':path=self.out/'queue.json';field='boot_id';value='other'
            elif mode=='stop':path=self.out/'server-stop.json';field='stop_confirmed';value=False
            else:path=self.out/'cards-released.json';field='verified';value=False
            original=runner.read(path);changed=copy.deepcopy(original);changed[field]=value;q.atomic(path,changed)
            with self.subTest(mode=mode),self.assertRaises(RuntimeError):runner.previous_receipts(self.out)
            q.atomic(path,original)
        self.restore.assert_not_called()

    def test_history_unit_conflict_is_checked_without_self_conflict(self):
        response=SimpleNamespace(stdout='ctx-history-study-v1.service loaded active running x\n')
        with patch.object(q,'release_reason',return_value=None),patch.object(q,'read_command',return_value=response) as inspect:
            self.assertIsNotNone(runner.release_reason({}))
            self.assertIn('ctx-history-study-v1.service',inspect.call_args.args[0])
            self.assertNotIn('ctx-full-source-v1.service',inspect.call_args.args[0])

    def test_all_exact_with_unknown_cache_cannot_supply_negative_cost_admission(self):
        audit=copy.deepcopy(self.audit)
        audit['trials']=[{'quality_passed':True,'cold_cost_interpretation':False,'total_trial_wall_seconds':1} for _ in range(8)]
        q.atomic(self.out/'diagnostic-independent-audit.json',audit)
        with self.assertRaisesRegex(RuntimeError,'negative cost signal'):runner.previous_receipts(self.out)
        self.restore.assert_not_called()

    def test_prior_health_command_and_controlflow_pins_are_checked(self):
        original=runner.read(self.out/'postflight-health.command.json')
        for change in ({'argv':['true']},{'argv':original['argv'],'exit_code':1}):
            q.atomic(self.out/'postflight-health.command.json',change)
            with self.assertRaises(RuntimeError):runner.previous_receipts(self.out)
        q.atomic(self.out/'postflight-health.command.json',original)
        queue=runner.read(self.out/'queue.json');queue['dependency_sha256']={};q.atomic(self.out/'queue.json',queue)
        with self.assertRaisesRegex(RuntimeError,'control flow'):runner.previous_receipts(self.out)


class ResultsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.out=Path(self.temp.name);self.p=packet();self.packetdir=self.out/'packet';self.packetdir.mkdir()
        q.atomic(self.packetdir/'plan.json',self.p['plan'])
        self.launch=self.out/'launch.json';q.atomic(self.launch,profile())
        self.config={'packet':str(self.packetdir),'expected_trials':self.p['plan']['trials'],'port':18196,'model':runner.MODEL}
        self.identity={'endpoint':'http://127.0.0.1:18196/v1','model':runner.MODEL,'launch_sha256':q.sha(self.launch)}

    def write(self,failed=0):
        d=self.out/'diagnostic';d.mkdir(exist_ok=True);rows=[];audits=[]
        for index,item in enumerate(self.p['plan']['trials']):
            state='failed' if index<failed else 'completed';path=d/item['result_path'];path.parent.mkdir(exist_ok=True)
            native={'schema':'full-source-trial.v1','protocol':runner.PROTOCOL,**item,**runner.POLICY,
                'measurement_kind':'model','resumed':False,'server_identity':self.identity,
                'source_code_sha256':self.p['plan']['source_code_sha256'],'status':state,'failure_kind':None}
            q.atomic(path,native);q.atomic(d/item['timing_path'],{'result_sha256':q.sha(path)})
            row={**item,'status':state,'result_sha256':q.sha(path),'timing_sha256':q.sha(d/item['timing_path'])}
            rows.append(row);audits.append({**row,'checkpoint_quality':None,'event_quality':None})
        summary={'schema':'full-source-summary.v1','protocol':runner.PROTOCOL,'measurement_kind':'model',
            'expected_trials':2,'completed_trials':2-failed,'failed_trials':failed,'unstarted_trials':[],
            'infrastructure_abort':False,'server_identity':self.identity,'trials':rows,
            'source_code_sha256':self.p['plan']['source_code_sha256'],'plan_sha256':q.sha(self.packetdir/'plan.json'),
            'speed_gate_passed':False,'holdout_admitted':False}
        q.atomic(d/'summary.json',summary)
        audit={'schema':'full-source-native-audit.v1','protocol':runner.PROTOCOL,'output':str(self.out),
            'measurement_kind':'model','packet_plan_sha256':q.sha(self.packetdir/'plan.json'),'infrastructure_abort':False,
            'planned_trials':2,'completed_trials':2-failed,'failed_trials':failed,'unstarted_trials':0,'incomplete_trials':0,
            'trials':audits,'speed_gate_passed':False,'holdout_admitted':False}
        return summary,audit

    def test_all_terminal_model_failures_are_kept(self):
        for failed in (0,1,2):
            summary,audit=self.write(failed)
            with patch.object(q,'run_evidence_audit',return_value=audit):
                self.assertEqual(runner.verify_results(self.out,self.config,self.launch)['failed_trials'],failed)

    def test_stub_partial_infrastructure_identity_and_count_refused(self):
        for field,bad in [('measurement_kind','stub'),('infrastructure_abort',True),('failed_trials',None),
                          ('server_identity',{}),('unstarted_trials',['t02-theatre']),('speed_gate_passed',True)]:
            summary,audit=self.write();summary[field]=bad;q.atomic(self.out/'diagnostic/summary.json',summary)
            with patch.object(q,'run_evidence_audit',return_value=audit):
                with self.subTest(field=field),self.assertRaises(RuntimeError):runner.verify_results(self.out,self.config,self.launch)

    def test_native_resumed_policy_tamper_and_audit_hash_refused(self):
        for mode in ('resumed','policy','hash'):
            summary,audit=self.write();row=summary['trials'][0];p=self.out/'diagnostic'/row['result_path']
            value=runner.read(p)
            if mode=='resumed':value['resumed']=True
            elif mode=='policy':value['max_requests_per_trial']=1.0
            else:audit['trials'][0]['result_sha256']='wrong'
            q.atomic(p,value)
            with patch.object(q,'run_evidence_audit',return_value=audit):
                with self.subTest(mode=mode),self.assertRaises(RuntimeError):runner.verify_results(self.out,self.config,self.launch)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.out=Path(self.temp.name);self.p=packet();self.profile=profile()
        self.config={'schema':runner.QUEUE_SCHEMA,'protocol':runner.PROTOCOL,'cache_policy':runner.CACHE_POLICY,
            'packet':'/fixture','expected_trials':self.p['plan']['trials'],'max_wait_seconds':0,'port':18196,
            'model':runner.MODEL,'effective_profile':q.effective_profile(self.profile),
            'server_args':q.profile_args(self.profile),'expected_launch_identity':{k:self.profile[k]for k in ('overlay_sha256','reference_sha256','guard_sha256')}}
        q.atomic(self.out/'queue.json',self.config);q.atomic(self.out/'status.json',{'phase':'prepared'})
        self.server=Mock();self.server.out=self.out/'server';self.server.out.mkdir();q.atomic(self.server.out/'launch.json',self.profile)
        self.commands=[];self.held=[];self.lock_entries=[];self.fail=None;self.gpu_fault=False
        def stop():
            self.assertIn(q.MODEL_LOCK,self.held)
            return {'stop_confirmed':True}
        self.server.stop.side_effect=stop
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        @contextmanager
        def lock(path):
            self.assertNotIn(path,self.held);self.held.append(path);self.lock_entries.append(path)
            try:yield
            finally:self.held.remove(path)
        def command(args,name,out,config,**kwargs):
            self.commands.append(name)
            q.atomic(out/(name+'.command.json'),{'argv':list(map(str,args))})
            if name in ('preflight-health','postflight-health'):self.assertIn(q.STAGE_LOCK,self.held)
            if name=='diagnostic':self.assertIn(q.MODEL_LOCK,self.held)
            if name=='strict-compare':q.atomic(out/'strict-comparison.json',strict())
            if name==self.fail:raise RuntimeError('injected '+name)
        def construct(*args):
            self.assertNotIn(q.STAGE_LOCK,self.held);return self.server
        def fault(*args):
            if self.gpu_fault:raise RuntimeError('known GPU fault')
        for name,value in {'file_lock':lock,'fault_check':fault,'resource_check':Mock(),
                           'load_helper':Mock(),'wait_available':Mock(),'monitored_command':command,
                           'status':lambda out,phase,**kw:q.atomic(out/'status.json',{'phase':phase,**kw}),
                           'STOP_REQUESTED':False}.items():self.stack.enter_context(patch.object(q,name,value))
        self.owner=self.stack.enter_context(patch.object(q,'OwnedServer',side_effect=construct))
        self.stack.enter_context(patch.object(runner,'verify_dependencies'))
        self.stack.enter_context(patch.object(runner,'validate_packet',return_value=self.p))
        self.stack.enter_context(patch.object(runner,'release_reason',return_value=None))
        def verify(*args):
            self.assertIn(q.MODEL_LOCK,self.held)
            return {'completed_trials':1,'failed_trials':1}
        self.stack.enter_context(patch.object(runner,'verify_results',side_effect=verify))

    def test_exactly_one_owner_two_request_client_then_stop_and_health(self):
        runner.execute(self.out)
        self.owner.assert_called_once();self.server.stop.assert_called_once()
        self.assertEqual(self.commands,['preflight-health','strict','strict-compare','diagnostic','postflight-health'])
        self.assertEqual(runner.read(self.out/'status.json')['phase'],'completed')
        with self.assertRaisesRegex(RuntimeError,'already started'):runner.execute(self.out)
        self.owner.assert_called_once()

    def test_preflight_failure_never_launches(self):
        self.fail='preflight-health'
        with self.assertRaises(RuntimeError):runner.execute(self.out)
        self.owner.assert_not_called();self.server.stop.assert_not_called()
        self.assertEqual(runner.read(self.out/'status.json')['phase'],'failed')

    def test_client_failure_stops_owned_server_without_retry(self):
        self.fail='diagnostic'
        with self.assertRaisesRegex(RuntimeError,'injected diagnostic'):runner.execute(self.out)
        self.owner.assert_called_once();self.server.stop.assert_called_once()
        self.assertIn('postflight-health',self.commands)
        self.assertTrue((self.out/'cards-released.json').is_file())
        status=runner.read(self.out/'status.json');self.assertEqual(status['phase'],'failed')
        self.assertTrue(status['postflight_passed']);self.assertEqual(runner.read(self.out/'postflight-health.exit.json')['exit_code'],0)

    def test_strict_failure_leaves_two_request_client_untouched(self):
        self.fail='strict'
        with self.assertRaises(RuntimeError):runner.execute(self.out)
        self.assertNotIn('diagnostic',self.commands);self.server.stop.assert_called_once()

    def test_actual_cache_override_refused_before_strict_requests(self):
        self.profile['argv'].append('--enable-prefix-caching');q.atomic(self.server.out/'launch.json',self.profile)
        with self.assertRaises(RuntimeError):runner.execute(self.out)
        self.assertNotIn('strict',self.commands);self.server.stop.assert_called_once()

    def test_cleanup_failure_retains_original_client_failure(self):
        self.fail='diagnostic';self.server.stop.side_effect=RuntimeError('STOP failed')
        with self.assertRaisesRegex(RuntimeError,'injected diagnostic'):runner.execute(self.out)
        status=runner.read(self.out/'status.json');self.assertEqual(status['phase'],'cleanup-failed')
        self.assertIn('injected diagnostic',status['original_error']);self.assertIn('STOP failed',status['error'])

    def test_postflight_failure_records_terminal_failure(self):
        self.fail='postflight-health'
        with self.assertRaisesRegex(RuntimeError,'postflight-health'):runner.execute(self.out)
        self.assertEqual(runner.read(self.out/'status.json')['phase'],'failed');self.server.stop.assert_called_once()

    def test_known_gpu_fault_blocks_postflight_device_probe(self):
        def stop():
            self.gpu_fault=True
            return {'stop_confirmed':True}
        self.server.stop.side_effect=stop
        with self.assertRaisesRegex(RuntimeError,'known GPU fault'):runner.execute(self.out)
        self.assertNotIn('postflight-health',self.commands)
        self.assertTrue((self.out/'cards-released.json').is_file())

    def test_model_lease_is_continuous_through_audit_stop_and_postflight(self):
        runner.execute(self.out)
        self.assertEqual(self.held,[])
        self.assertEqual(self.lock_entries.count(q.MODEL_LOCK),1)
        self.assertTrue((self.out/'postflight-health.exit.json').is_file())


if __name__=='__main__':unittest.main()
