"""CPU intercepted lifecycle checks: no actual service, queue or privileged call."""
from contextlib import ExitStack
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


def load(name,filename):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(filename))
    mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod


D=load('p200_driver_test','driver.py');R=load('p200_restore_test','restore_guard.py')
T=load('p200_frozen_contract_tests','test_window.py')
S=D.S


class DriverTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.queue=self.root/'queue';self.queue.mkdir()
        self.output=self.root/'worker';self.review=self.root/'review.json';self.evidence=self.root/'window'
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        for key,value in [('QUEUE',self.queue),('OUTPUT',self.output),('REVIEW',self.review),('EXPECTED_MANIFEST_SHA',None),('CLIENT_RESULT',self.root/'client/client-result.json')]:
            self.stack.enter_context(patch.object(D,key,value))
        for lane in ('A','B'):
            (self.queue/f'PAUSE-{lane}').write_text('original '+lane+'\n');(self.queue/f'queue-{lane}.txt').write_text('')
        self.window=D.Window(self.evidence,'20261023-restore29')
        self.window.pause={l:(self.queue/f'PAUSE-{l}').read_bytes() for l in ('A','B')}
        self.plan={'profile':{'limits':dict(host_required_available_bytes=1,coordinator_margin_bytes=1,
                   disk_floor_bytes=27_000_000_000,planned_write_bytes=1)}}
        # An unexpected operation must fail even in a test's early-refusal path.
        self.command=self.stack.enter_context(patch.object(S,'command',side_effect=AssertionError('unmocked operation')))

    def setup_execute(self):
        self.stack.enter_context(patch.object(D,'check',return_value=dict(plan=self.plan,worker_sha256='mock',
            manifest_sha256='hash',staging_identity={})))
        self.stack.enter_context(patch.object(D,'plan',return_value=self.plan))
        self.stack.enter_context(patch.object(D,'clear'))
        self.stack.enter_context(patch.object(D,'safe_stop'))
        self.stack.enter_context(patch.object(S,'sha',return_value='mock'))
        self.stack.enter_context(patch.object(S,'endpoint_idle'))
        self.stack.enter_context(patch.object(S,'require_drained',return_value={'mock':True}))
        self.stack.enter_context(patch.object(S,'active',return_value=False))
        self.stack.enter_context(patch.object(D.C,'require_same_staging_identity'))
        self.stack.enter_context(patch.object(D.H,'verify'))
        self.stack.enter_context(patch.object(D.shutil,'disk_usage',return_value=type('Usage',(),{'free':40_000_000_000})()))
        def command(argv,**kw):
            if '--capture-fault-review' in argv:self.review.write_text('{}')
            return subprocess.CompletedProcess(argv,0,'','')
        self.command.side_effect=command
        self.restore=self.stack.enter_context(patch.object(D.subprocess,'run',return_value=subprocess.CompletedProcess([],0)))

    def result(self,count=2):
        row=T.terminal(count);row['plan_sha256']=D.C.digest(self.plan)
        pre=copy.deepcopy(row);pre.update(passed=False,evidence_passed=False,writers_closed=False,
                                         coordination_completed=False,precompletion_written=False)
        return row,pre

    def files(self,count=2):
        row,pre=self.result(count);path=self.output/'terminal';path.mkdir(parents=True)
        (path/'worker.json').write_text(json.dumps(row));(path/'pre-completion.json').write_text(json.dumps(pre))
        return row,pre

    def test_missing_manifest_before_commands_locks_or_latches_for_both_modes(self):
        with patch.object(D.A,'MANIFEST',self.root/'absent'),patch.object(S,'locked') as lock:
            for mode in ('--check','--run'):
                with patch.object(sys,'argv',['driver',mode,'--restore-suffix','20261023-restore29','--output',str(self.evidence)]):
                    with self.assertRaises(FileNotFoundError):D.main()
            lock.assert_not_called();self.command.assert_not_called()
        self.assertFalse(self.evidence.exists());self.assertTrue((self.queue/'PAUSE-A').exists())

    def test_one_launch_one_restore_and_exact_pause_preservation(self):
        self.setup_execute()
        with patch.object(self.window,'watch',return_value={'validation':{'lifecycle_only':False}}):self.window.execute()
        calls=[c.args[0] for c in self.command.call_args_list]
        self.assertEqual(len([c for c in calls if c[0]=='systemd-run']),1)
        self.assertEqual(len([c for c in calls if c[:3]==['systemctl','--user','stop']]),3)
        launch=next(c for c in calls if c[0]=='systemd-run')
        self.assertIn('--property=Nice=0',launch);self.assertIn('0-3,16-19',launch)
        self.assertIn('--property=SendSIGKILL=no',launch)
        self.restore.assert_called_once();self.assertIn('--manifest-sha256',self.restore.call_args.args[0])
        for lane in ('A','B'):self.assertEqual((self.queue/f'PAUSE-{lane}').read_bytes(),self.window.pause[lane])

    def test_failed_worker_stops_intake_without_restore(self):
        self.setup_execute();self.output.mkdir()
        with patch.object(self.window,'watch',side_effect=RuntimeError('original fault')):
            with self.assertRaisesRegex(RuntimeError,'original fault'):self.window.execute()
        self.restore.assert_not_called();self.assertTrue((self.queue/'STOP-A').exists());self.assertTrue((self.output/'STOP').exists())

    def test_unknown_postflight_owner_refuses_restore(self):
        self.setup_execute()
        with patch.object(self.window,'watch',return_value={}),patch.object(S,'require_drained',side_effect=[{},RuntimeError('unknown owner')]):
            with self.assertRaisesRegex(RuntimeError,'unknown owner'):self.window.execute()
        self.restore.assert_not_called()

    def test_forecast_rechecked_postdrain_before_capture_or_launch(self):
        self.setup_execute()
        with patch.object(D.shutil,'disk_usage',return_value=type('Usage',(),{'free':26_999_999_999})()):
            with self.assertRaisesRegex(RuntimeError,'storage floor'):self.window.execute()
        self.restore.assert_not_called()
        self.assertFalse(any('--capture-fault-review' in c.args[0] or c.args[0][0]=='systemd-run' for c in self.command.call_args_list))

    def test_incident_preserves_external_pause_and_sends_only_one_main_sigterm(self):
        self.evidence.mkdir();self.window.launched=True;(self.queue/'PAUSE-B').write_text('external\n')
        self.command.side_effect=None;self.command.return_value=subprocess.CompletedProcess([],0,'','')
        with patch.object(D,'safe_stop'),patch.object(S,'active',return_value=True),patch.object(D.time,'monotonic',side_effect=[0,901,0,901]):
            for _ in range(2):
                with self.assertRaisesRegex(RuntimeError,'retained after drain'):self.window.incident()
        self.command.assert_called_once()
        self.assertIn('--kill-whom=main',self.command.call_args.args[0]);self.assertIn('--signal=SIGTERM',self.command.call_args.args[0])
        self.assertEqual((self.queue/'PAUSE-B').read_text(),'external\n')

    def test_terminal_binds_both_receipts_and_separate_drain(self):
        self.files();state=dict(ActiveState='inactive',Result='success',ExecMainStatus='0')
        self.assertTrue(D.terminal(self.plan,state,passive_drained=True)['validation']['passed'])
        with self.assertRaisesRegex(RuntimeError,'drain'):D.terminal(self.plan,state,passive_drained=False)
        pre=self.output/'terminal/pre-completion.json';row=json.loads(pre.read_text());row['controls']=0;pre.write_text(json.dumps(row))
        with self.assertRaisesRegex(RuntimeError,'identity differs'):D.terminal(self.plan,state,passive_drained=True)

    def test_zero_requests_explicit_lifecycle_only(self):
        self.files(0)
        result=D.terminal(self.plan,dict(ActiveState='inactive',Result='success',ExecMainStatus='0'),passive_drained=True)
        self.assertTrue(result['validation']['lifecycle_only'])

    def test_failed_unit_cannot_be_masked_by_good_json(self):
        self.files();(self.queue/'PAUSE-A').unlink()
        with patch.object(D,'clear'),patch.object(D,'status',return_value=dict(ActiveState='failed',Result='exit-code',ExecMainStatus='1')):
            with self.assertRaisesRegex(RuntimeError,'unit did not succeed'):self.window.watch(self.plan)

    def test_watch_waits_for_physical_drain_before_validating_receipts(self):
        self.files();self.evidence.mkdir();(self.queue/'PAUSE-A').unlink();self.window.client_launched=True
        with patch.object(D,'clear'),patch.object(D,'status',return_value=dict(ActiveState='inactive',Result='success',ExecMainStatus='0')),patch.object(D,'client_terminal',return_value={}),patch.object(S,'require_drained',side_effect=RuntimeError('physical owner')),patch.object(D,'terminal') as terminal:
            with self.assertRaisesRegex(RuntimeError,'physical owner'):self.window.watch(self.plan)
            terminal.assert_not_called()

    def test_safe_stop_refuses_group_kill_mode(self):
        with patch.object(S,'require_safe_stop',return_value={'KillMode':'control-group'}):
            with self.assertRaisesRegex(RuntimeError,'process-only'):D.safe_stop('mock')

    def test_restore_namespace_and_validation_child_keep_manifest_guard(self):
        original=sys.modules.get('window');sentinel=object();sys.modules['window']=sentinel
        self.addCleanup(lambda:sys.modules.pop('window',None) if original is None else sys.modules.__setitem__('window',original))
        def inherited(path,**kw):
            self.assertIs(sys.modules['window'],R.D)
            from window import faults_clear
            self.assertEqual(faults_clear.__name__,'restore_clear')
            subprocess.run(['/usr/bin/python3',str(R.D.H.PARENT/'validate.py'),'--base','http://mock'])
        with patch.object(R.D,'admission',return_value=({'controller':{'restore_suffix':'20261023-restore29'}},'hash')),patch.object(R.D.H,'verify'),patch.object(R.D,'restore_clear'),patch.object(R,'admit_restore'),patch.object(R.runpy,'run_path',side_effect=inherited),patch.object(subprocess,'run',return_value=subprocess.CompletedProcess([],0)) as run:
            R.main(['--manifest-sha256','hash','20261023-restore29'])
        self.assertIs(sys.modules['window'],sentinel)
        self.assertEqual(run.call_args.args[0][3:7],['--manifest-sha256','hash','--validate','--base'])
        self.assertEqual(D.C.OPERATIONAL_ENTRYPOINT_ENABLED,False)

    def test_direct_restore_rejects_retained_worker_before_parent_execution(self):
        self.evidence.mkdir()
        (self.evidence/'preflight.json').write_text(json.dumps({'manifest_sha256':'hash','plan':self.plan}))
        manifest={'controller':{'evidence':str(self.evidence),'restore_suffix':'20261023-restore29'},'plan_sha256':D.C.digest(self.plan)}
        with patch.object(R.D,'EXPECTED_MANIFEST_SHA','hash'),patch.object(R.D,'status',return_value={'ActiveState':'active'}),patch.object(R.D.S,'require_drained') as drain:
            with self.assertRaisesRegex(RuntimeError,'worker must exit'):R.admit_restore(manifest,False,['20261023-restore29'])
            drain.assert_not_called()
        self.assertFalse((self.evidence/'restore-admission.json').exists())

    def test_direct_restore_bad_precompletion_refuses_before_marker(self):
        self.evidence.mkdir()
        (self.evidence/'preflight.json').write_text(json.dumps({'manifest_sha256':'hash','plan':self.plan}))
        manifest={'controller':{'evidence':str(self.evidence),'restore_suffix':'20261023-restore29'},'plan_sha256':D.C.digest(self.plan)}
        with patch.object(R.D,'EXPECTED_MANIFEST_SHA','hash'),patch.object(R.D,'status',return_value=dict(ActiveState='inactive',Result='success',ExecMainStatus='0')),patch.object(R.D.S,'require_drained',return_value={}),patch.object(R.D,'terminal',side_effect=RuntimeError('bad precompletion')):
            with self.assertRaisesRegex(RuntimeError,'bad precompletion'):R.admit_restore(manifest,False,['20261023-restore29'])
        self.assertFalse((self.evidence/'restore-admission.json').exists())

    def test_successful_parent_exit_does_not_hide_final_guard_failure(self):
        with patch.object(R.D,'admission',return_value=({'controller':{}},'hash')),patch.object(R.D.H,'verify'),patch.object(R,'admit_restore'),patch.object(R.D,'restore_clear',side_effect=[None,RuntimeError('last guard')]),patch.object(R.runpy,'run_path',side_effect=SystemExit(0)):
            with self.assertRaisesRegex(RuntimeError,'last guard'):R.main(['--manifest-sha256','hash','suffix'])

    def test_client_extra_megabyte_reserved_before_host_actions(self):
        ops=self.root/'ops';(ops/'evidence').mkdir(parents=True);evidence=ops/'evidence/new'
        controller={'restore_suffix':'20261023-restore29','evidence':str(evidence),'staging_identity':{},'additional_write_bytes':1048576,'client_unit':D.CLIENT_UNIT,'client_receipt':str(D.CLIENT_RESULT),'qualification_requests':16}
        plan={'profile':{'limits':{'disk_floor_bytes':27000000000,'planned_write_bytes':768*1024**2}}}
        free=27000000000+768*1024**2+1048576-1
        with patch.object(D,'HERE',ops),patch.object(D,'admission',return_value=({'controller':controller},'hash')),patch.object(D.H,'verify'),patch.object(D.C,'staging_identity',return_value={}),patch.object(D,'plan',return_value=plan),patch.object(D.shutil,'disk_usage',return_value=type('Usage',(),{'free':free})()),patch.object(D,'clear') as clear:
            with self.assertRaisesRegex(RuntimeError,'planned writes'):D.check(controller['restore_suffix'],evidence)
            clear.assert_not_called();self.command.assert_not_called()

    def test_validation_refuses_arbitrary_target_and_replay(self):
        self.evidence.mkdir();manifest={'controller':{'evidence':str(self.evidence)}}
        with patch.object(R.D,'EXPECTED_MANIFEST_SHA','hash'):
            with self.assertRaisesRegex(RuntimeError,'exact inherited'):R.admit_restore(manifest,True,['--base','http://unadmitted'])
            (self.evidence/'restore-admission.json').write_text(json.dumps({'passed':True,'manifest_sha256':'hash'}))
            R.admit_restore(manifest,True,R.VALIDATIONS[0])
            with self.assertRaises(FileExistsError):R.admit_restore(manifest,True,R.VALIDATIONS[0])

    def test_restore_primary_failure_survives_final_guard_failure(self):
        primary=RuntimeError('original restore failure')
        with patch.object(R.D,'admission',return_value=({'controller':{}},'hash')),patch.object(R.D.H,'verify'),patch.object(R,'admit_restore'),patch.object(R.D,'restore_clear',side_effect=[None,RuntimeError('secondary guard')]),patch.object(R.runpy,'run_path',side_effect=primary):
            with self.assertRaisesRegex(RuntimeError,'original restore failure') as caught:R.main(['--manifest-sha256','hash','suffix'])
            self.assertIs(caught.exception,primary);self.assertIn('secondary guard',primary.__notes__[0])

    def test_missing_core_closure_and_orphan_capture_refuse_before_host_actions(self):
        ops=self.root/'ops';(ops/'evidence').mkdir(parents=True);evidence=ops/'evidence/new'
        controller={'restore_suffix':'20261023-restore29','evidence':str(evidence),'staging_identity':{},'additional_write_bytes':1048576,'client_unit':D.CLIENT_UNIT,'client_receipt':str(D.CLIENT_RESULT),'qualification_requests':16}
        with patch.object(D,'HERE',ops),patch.object(D,'admission',return_value=({'controller':controller},'hash')),patch.object(D.H,'verify'),patch.object(D.C,'staging_identity',return_value={}),patch.object(D,'plan',side_effect=RuntimeError('core closure missing')):
            with self.assertRaisesRegex(RuntimeError,'core closure missing'):D.check(controller['restore_suffix'],evidence)
            self.review.with_suffix('.kernel.jsonl.gz').write_bytes(b'orphan')
            with self.assertRaisesRegex(RuntimeError,'fresh coordinator'):D.check(controller['restore_suffix'],evidence)
        self.command.assert_not_called()

    def test_journal_failure_preserves_original_worker_fault(self):
        self.setup_execute()
        original=self.command.side_effect
        def command(argv,**kw):
            if argv[0]=='journalctl':raise OSError('journal timeout')
            return original(argv,**kw)
        self.command.side_effect=command
        error=RuntimeError('first worker failure')
        with patch.object(self.window,'watch',side_effect=error):
            with self.assertRaisesRegex(RuntimeError,'first worker failure') as caught:self.window.execute()
            self.assertIs(caught.exception,error);self.assertIn('journal timeout',error.__notes__[0])

    def test_restore_missing_manifest_refuses_before_runpy(self):
        with patch.object(R.D.A,'MANIFEST',self.root/'absent'),patch.object(R.runpy,'run_path') as parent:
            with self.assertRaises(FileNotFoundError):R.main(['--manifest-sha256','hash','20261023-restore29'])
            parent.assert_not_called()

    def test_restore_guard_checks_output_stop_and_original_pauses(self):
        self.evidence.mkdir()
        for lane,data in self.window.pause.items():(self.evidence/f'PAUSE-{lane}.before').write_bytes(data)
        with patch.object(D,'admission',return_value=({'controller':{'evidence':str(self.evidence)}},'hash')),patch.object(D.H,'verify'),patch.object(S,'faults_clear'):
            D.restore_clear();self.output.mkdir();(self.output/'STOP').write_text('fault')
            with self.assertRaisesRegex(RuntimeError,'incident latch'):D.restore_clear()

    def good_client(self):
        return dict(passed=True,requests=16,exact_recorded_requests=5,resumed_fresh_pairs=1,
                    maximum_output_tokens=1728,output_tokens=1728,controls_claimed=False,submission_eligible=False,speed_claim=False)

    def test_listener_launches_exactly_one_safe_helper_client(self):
        self.evidence.mkdir();self.command.side_effect=None
        self.command.return_value=subprocess.CompletedProcess([],0,'','')
        event={'event':'listener','address':['127.0.0.1',12345]}
        with patch.object(D,'clear'),patch.object(D,'admission'),patch.object(D,'status',return_value={'LoadState':'not-found'}):
            self.window.start_client(event)
            with self.assertRaisesRegex(RuntimeError,'already attempted'):self.window.start_client(event)
        self.command.assert_called_once();argv=self.command.call_args.args[0]
        self.assertIn('--unit=packet200-client-a',argv);self.assertIn('--property=Nice=19',argv)
        self.assertIn('8-15,24-31',argv);self.assertIn('--property=SendSIGKILL=no',argv)
        self.assertEqual(argv[-4:],[D.PYTHON,'-B',str(D.CLIENT_SCRIPT),'--execute'])

    def test_client_launch_failure_is_not_retried(self):
        self.evidence.mkdir();self.command.side_effect=None
        self.command.return_value=subprocess.CompletedProcess([],1,'','failure')
        with patch.object(D,'clear'),patch.object(D,'admission'),patch.object(D,'status',return_value={'LoadState':'not-found'}):
            with self.assertRaisesRegex(RuntimeError,'launch refused'):self.window.start_client({'address':['127.0.0.1',12345]})
            with self.assertRaisesRegex(RuntimeError,'already attempted'):self.window.start_client({'address':['127.0.0.1',12345]})
        self.command.assert_called_once()

    def test_client_terminal_refuses_every_count_scope_or_unit_mismatch(self):
        D.CLIENT_RESULT.parent.mkdir()
        state=dict(ActiveState='inactive',Result='success',ExecMainStatus='0')
        with patch.object(D,'client_provenance'):
            for key,value in [('requests',0),('requests',True),('exact_recorded_requests',4),('resumed_fresh_pairs',0),
                              ('output_tokens',1729),('submission_eligible',True),('speed_claim',True),('passed',False)]:
                row=self.good_client();row[key]=value;D.CLIENT_RESULT.write_text(json.dumps(row))
                with self.subTest(key=key,value=value),self.assertRaises(RuntimeError):D.client_terminal(state)
            D.CLIENT_RESULT.write_text(json.dumps(self.good_client()))
            self.assertTrue(D.client_terminal(state)['passed'])
            with self.assertRaisesRegex(RuntimeError,'client unit'):D.client_terminal(dict(ActiveState='active'))

    def test_client_provenance_binds_manifest_vectors_and_listener(self):
        D.CLIENT_RESULT.parent.mkdir();(self.output/'control').mkdir(parents=True)
        events=self.output/'control/events.jsonl';raw=b'{"event":"listener","address":["127.0.0.1",12345]}\n';events.write_bytes(raw)
        base=dict(manifest_sha256='hash',vectors_sha256='vectors',listener_events_sha256=D.hashlib.sha256(raw).hexdigest(),address=['127.0.0.1',12345])
        with patch.object(D,'admission',return_value=({},'hash')),patch.object(S,'sha',return_value='vectors'):
            for key in ('manifest_sha256','vectors_sha256','listener_events_sha256','address'):
                row=dict(base);row[key]='wrong';(D.CLIENT_RESULT.parent/'admission.json').write_text(json.dumps(row))
                with self.subTest(key=key),self.assertRaises(RuntimeError):D.client_provenance()
            (D.CLIENT_RESULT.parent/'admission.json').write_text(json.dumps(base))
            self.assertEqual(D.client_provenance(),base)

    def test_worker_exit_waits_for_client_final_validation_before_physical_drain(self):
        self.evidence.mkdir();(self.queue/'PAUSE-A').unlink();self.window.client_launched=True
        inactive=dict(ActiveState='inactive',Result='success',ExecMainStatus='0')
        client_states=iter([{'ActiveState':'active'},inactive])
        calls=[]
        def status(unit=D.UNIT):return inactive if unit==D.UNIT else next(client_states)
        def sleep(_):calls.append('wait-client')
        def drain():calls.append('drain');return {}
        with patch.object(D,'clear'),patch.object(D,'status',side_effect=status),patch.object(D.time,'sleep',side_effect=sleep),patch.object(D,'client_terminal',return_value=self.good_client()),patch.object(S,'require_drained',side_effect=drain),patch.object(D,'qualification',return_value={'qualified':True}):
            self.assertEqual(self.window.watch(self.plan),{'qualified':True})
        self.assertEqual(calls,['wait-client','drain'])

    def test_client_failure_halts_worker_and_never_restores(self):
        self.setup_execute();self.output.mkdir();self.window.client_launched=True
        def status(unit=D.UNIT):
            return {'ActiveState':'active'} if unit==D.UNIT else dict(ActiveState='failed',Result='exit-code',ExecMainStatus='1')
        with patch.object(D,'status',side_effect=status):
            with self.assertRaisesRegex(RuntimeError,'client unit did not succeed'):self.window.execute()
        self.assertTrue((self.queue/'STOP-A').exists());self.assertTrue((self.output/'STOP').exists())
        self.restore.assert_not_called()

    def test_empty_worker_is_not_serving_qualification(self):
        row,pre=self.result(0)
        with patch.object(D,'terminal',return_value={'worker':row}),patch.object(D,'client_terminal') as client:
            with self.assertRaisesRegex(RuntimeError,'sixteen'):D.qualification(self.plan,{},passive_drained=True)
            client.assert_not_called()

    def test_direct_restore_waits_for_client_even_after_worker_success(self):
        self.evidence.mkdir();(self.evidence/'preflight.json').write_text(json.dumps({'manifest_sha256':'hash','plan':self.plan}))
        manifest={'controller':{'evidence':str(self.evidence),'restore_suffix':'20261023-restore29'},'plan_sha256':D.C.digest(self.plan)}
        good=dict(ActiveState='inactive',Result='success',ExecMainStatus='0')
        def status(unit=R.D.UNIT):return good if unit==R.D.UNIT else {'ActiveState':'active'}
        with patch.object(R.D,'EXPECTED_MANIFEST_SHA','hash'),patch.object(R.D,'status',side_effect=status),patch.object(R.D.S,'require_drained',return_value={}),patch.object(R.D,'terminal',return_value={'worker':{'requests':16,'controls':16}}):
            with self.assertRaisesRegex(RuntimeError,'client unit must exit'):R.admit_restore(manifest,False,['20261023-restore29'])
        self.assertFalse((self.evidence/'restore-admission.json').exists())


if __name__=='__main__':unittest.main()
