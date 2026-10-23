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
        for key,value in [('QUEUE',self.queue),('OUTPUT',self.output),('REVIEW',self.review),('EXPECTED_MANIFEST_SHA',None)]:
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
        self.files();self.evidence.mkdir();(self.queue/'PAUSE-A').unlink()
        with patch.object(D,'clear'),patch.object(D,'status',return_value=dict(ActiveState='inactive',Result='success',ExecMainStatus='0')),patch.object(S,'require_drained',side_effect=RuntimeError('physical owner')),patch.object(D,'terminal') as terminal:
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
            self.assertEqual(faults_clear,R.D.restore_clear)
            subprocess.run(['/usr/bin/python3',str(R.D.H.PARENT/'validate.py'),'--base','http://mock'])
        with patch.object(R.D,'admission',return_value=({'controller':{'restore_suffix':'20261023-restore29'}},'hash')),patch.object(R.D.H,'verify'),patch.object(R.D,'restore_clear'),patch.object(R.runpy,'run_path',side_effect=inherited),patch.object(subprocess,'run',return_value=subprocess.CompletedProcess([],0)) as run:
            R.main(['--manifest-sha256','hash','20261023-restore29'])
        self.assertIs(sys.modules['window'],sentinel)
        self.assertEqual(run.call_args.args[0][3:7],['--manifest-sha256','hash','--validate','--base'])
        self.assertEqual(D.C.OPERATIONAL_ENTRYPOINT_ENABLED,False)

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


if __name__=='__main__':unittest.main()
