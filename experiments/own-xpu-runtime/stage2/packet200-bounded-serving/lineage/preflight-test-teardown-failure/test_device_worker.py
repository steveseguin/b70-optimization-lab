"""CPU-only orchestration and interception; never execute a native owner."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('p200_worker_tests',HERE/'device_worker.py')
W=importlib.util.module_from_spec(spec);spec.loader.exec_module(W)


class Pipe:
    def __init__(self):self.closed=False
    def fileno(self):return 45
    def close(self):self.closed=True


class Process:
    def __init__(self,argv):
        self.args=argv;self.pid=12345;self.stdin=Pipe();self.stdout=Pipe();self.stderr=Pipe()
        self.returncode=None;self.signals=[];self.exit_on_signal=True
    def poll(self):return self.returncode
    def send_signal(self,number):
        self.signals.append(number)
        if self.exit_on_signal:self.returncode=0
    def wait(self,timeout):
        if self.returncode is None:raise subprocess.TimeoutExpired(self.args,timeout)
        return self.returncode


class Safety:
    def __init__(self,events):self.events=events;self.completed=False;self.released=False;self.fail_after_ready=None;self.acquire_error=None;self.on_complete=None
    def preflight(self):self.events.append('preflight');return 'initial kernel\n'
    def acquire(self,guard):
        self.events.append('acquire')
        if self.acquire_error:raise self.acquire_error
    def before_launch(self):self.events.append('before-launch')
    def environment(self):return {'OMP_NUM_THREADS':'2','FilterBdfPath':'0000:23:00.0'}
    def store_environment(self):return {}
    def check(self,run):
        if run.front is not None and self.fail_after_ready is not None:raise self.fail_after_ready
    def register(self,child):self.events.append('register')
    def ready(self,child):self.events.append('ready')
    def postflight(self):self.events.append('postflight')
    def complete(self):
        if self.on_complete:self.on_complete()
        self.completed=True
    def release(self):self.released=True


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=HERE,prefix='cpu-worker-');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.events=[];self.clock=1000.0;self.count=2;self.model_loads=1;self.stop_count_delta=0
        self.profile=dict(paths=dict(output=str(self.root/'output'),checkpoint_root=str(self.root/'checkpoints'),owner_output=str(self.root/'output/owner')),
            limits=dict(requests=16,context=4096,vocab=248320,max_new=512,idle_seconds=240,absolute_seconds=4800,native_seconds=7200),
            binary=dict(path='/synthetic/never-executed',sha256='a'*64),native_argv=['/usr/bin/ionice','-c3','/synthetic/never-executed'])
        self.plan=dict(profile=self.profile,activity_mode='launch')
        self.process=Process(self.profile['native_argv']);self.safety=Safety(self.events)
        self.diag_retained=False;self.diag_fail=None;self.diag_incident=None;self.advance_load=0
        test=self
        class Diagnostics:
            def __init__(self,*args):
                self.incident_event=threading.Event();self.error=None;self.started=False
            def start(self):
                test.events.append('diagnostics-start');self.started=True
                if test.diag_incident:self.error=test.diag_incident;self.incident_event.set()
                if test.diag_fail:raise test.diag_fail
                return self
            def status(self):
                return dict(started=self.started,eof=test.process.poll() is not None,
                    retained=test.diag_retained,reader_retained=False,capture_retained=test.diag_retained,
                    owned_read_fd_open=test.diag_retained,reader_startup_uncertain=False,
                    incident=self.incident_event.is_set(),bytes_read=0,successful_append_bytes=0,definitely_discarded_bytes=0)
            def join(self,timeout):return self.status()
        class Front:
            def __init__(self,child,**kw):
                test.events.append('front-ready');self.ready={'model_loads':test.model_loads};self.completed=self.completed_controls=0
                self.state='ready';self.pending=None;self.process=child;test.clock+=test.advance_load
                output=Path(test.profile['paths']['owner_output']);output.mkdir()
                (output/'receipt.json').write_text(json.dumps(dict(passed=True,safe_to_exit=True,device_executed=True)))
            def close(self,timeout):
                test.events.append('front-close');self.process.returncode=0;self.state='closed'
                return dict(event='stopped',safe_to_exit=True,reason='request-limit' if self.completed==16 else 'quit',
                    completed_requests=self.completed+test.stop_count_delta,completed_controls=self.completed_controls,discarded_pending=False,pending_request_id='')
        class Store:
            def __init__(self,*args):self.closed=False
            def close(self):self.closed=True
        class Session:
            def __init__(self,front):self.front=front;self.close_requested=False
            def request_close(self):self.close_requested=True
            def open_listener(self,address):test.events.append('listener');return ('127.0.0.1',1234)
            def serve(self):
                self.front.completed=self.front.completed_controls=test.count
                stopped=self.front.close(120)
                return dict(passed=True,lifecycle={'native_stopped':stopped})
        patches=[patch.object(W,'PipeDiagnostics',Diagnostics),patch.object(W,'NativeFront',Front),
            patch.object(W,'NativeCheckpointStore',Store),patch.object(W.session_module,'attach',side_effect=lambda profile,**kw:Session(kw['front'])),
            patch.object(W,'helper_placement',side_effect=lambda:self.assertNotEqual(threading.get_ident(),self.main_thread)),
            patch.object(W,'native_placement',return_value=None),patch.object(W.time,'monotonic',side_effect=lambda:self.clock),
            patch.object(W.subprocess,'Popen',side_effect=self.popen)]
        self.main_thread=threading.get_ident()
        for mock in patches:mock.start();self.addCleanup(mock.stop)
        self.popen_calls=[];self.popen_error=None

    def popen(self,*args,**kwargs):
        self.popen_calls.append((args,kwargs));self.events.append('popen')
        if self.popen_error:raise self.popen_error
        return self.process

    def run_worker(self):
        self.run=W.OwnedRun(self.plan,self.safety);return self.run.run()

    def tearDown(self):
        # Synthetic retained cases have no live process/thread. Explicit test
        # disposal is outside production code and is not a recovery mechanism.
        run=getattr(self,'run',None)
        if run:
            run.stop_monitor.set()
            if run.monitor_thread and run.monitor_thread.ident:run.monitor_thread.join(1)
            for writer in (run.stderr_writer,run.control,run.terminal):
                if writer:writer.close()

    def test_full_single_popen_interception_and_normal_cleanup(self):
        row=self.run_worker();self.assertTrue(row['passed']);self.assertFalse(row['retained'])
        self.assertEqual(len(self.popen_calls),1)
        args,kwargs=self.popen_calls[0];self.assertEqual(args,(self.profile['native_argv'],))
        self.assertEqual(kwargs,dict(env=self.safety.environment(),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE))
        self.assertLess(self.events.index('diagnostics-start'),self.events.index('register'))
        self.assertLess(self.events.index('diagnostics-start'),self.events.index('front-ready'))
        self.assertEqual(self.events.count('front-close'),1);self.assertEqual(self.process.signals,[])
        self.assertTrue(self.safety.completed);self.assertTrue(self.safety.released);self.assertTrue(self.run.store.closed)
        saved=json.loads((self.root/'output/terminal/worker.json').read_text())
        self.assertTrue(saved['coordination_completed']);self.assertTrue(saved['writers_closed']);self.assertEqual(saved['requests'],2)

    def test_actual_pipe_drainer_and_bounded_writer_join(self):
        from native_diagnostics import PipeDiagnostics
        read_fd,write_fd=os.pipe();self.process.stderr=os.fdopen(read_fd,'rb',buffering=0)
        payload=b'actual CPU pipe diagnostic\n'
        os.write(write_fd,payload);os.close(write_fd)
        with patch.object(W,'PipeDiagnostics',PipeDiagnostics):row=self.run_worker()
        self.assertTrue(row['passed']);self.assertTrue(row['diagnostics_finished'])
        self.assertEqual((self.root/'output/stderr/native.stderr.log').read_bytes(),payload)
        status=row['diagnostics'];self.assertTrue(status['eof']);self.assertFalse(status['retained'])
        self.assertFalse(status['reader_retained']);self.assertFalse(status['capture_retained'])
        self.assertFalse(status['owned_read_fd_open']);self.assertTrue(self.process.stderr.closed)
        self.assertEqual(status['successful_append_bytes'],len(payload))

    def test_preflight_error_is_exposed_without_terminal_writer(self):
        original=RuntimeError('preflight refusal '+('x'*8000))
        self.safety.preflight=lambda:(_ for _ in ()).throw(original)
        with (patch.object(W,'authorize'),patch.object(W,'Safety',return_value=self.safety),
              patch.object(W.signal,'signal',return_value=None)):
            with self.assertRaises(W.WorkerFailure) as caught:W.execute(self.plan,fault_review=self.root/'absent')
        self.assertIs(caught.exception.original,original);self.assertLess(len(str(caught.exception)),4200)
        self.assertEqual(self.popen_calls,[]);self.assertFalse((self.root/'output').exists())

    def test_sixteen_requests_same_control_counts(self):
        self.count=16;row=self.run_worker();self.assertTrue(row['passed']);self.assertEqual(row['controls'],16)
        self.assertEqual(row['stopped']['reason'],'request-limit')

    def test_expired_unexposed_idle_closes_normally_without_store(self):
        self.advance_load=250;row=self.run_worker();self.assertTrue(row['passed'])
        self.assertFalse(row['listener_exposed']);self.assertEqual(row['requests'],0);self.assertIsNone(self.run.store)
        self.assertEqual(self.events.count('front-close'),1);self.assertFalse(self.process.signals)

    def test_diagnostics_start_failure_retains_original_endpoint(self):
        self.diag_fail=RuntimeError('reader startup uncertain');row=self.run_worker()
        self.assertTrue(row['retained']);self.assertFalse(row['passed']);self.assertFalse(self.process.stderr.closed)
        self.assertFalse(self.safety.completed);self.assertFalse(self.safety.released)
        self.assertEqual(len(self.process.signals),1);self.assertNotIn('listener',self.events)

    def test_capture_thread_retained_after_owner_exit_keeps_store_and_leases(self):
        self.diag_retained=True;row=self.run_worker()
        self.assertTrue(row['owner_exited']);self.assertTrue(row['retained']);self.assertFalse(self.run.store.closed)
        self.assertFalse(self.safety.completed);self.assertFalse(self.safety.released)
        self.assertFalse(self.run.stderr_writer.status()['closed'])

    def test_popen_exception_preserves_unknown_ownership_no_retry(self):
        self.popen_error=OSError('ambiguous spawn');row=self.run_worker()
        self.assertTrue(row['retained']);self.assertEqual(len(self.popen_calls),1);self.assertIsNone(self.run.child)
        self.assertFalse(self.safety.released);self.assertFalse(self.process.signals)

    def test_guard_fault_preserves_original_and_one_signal(self):
        error=RuntimeError('kernel fault');self.safety.fail_after_ready=error
        row=self.run_worker();self.run.incident(RuntimeError('second error'))
        self.assertIs(self.run.first_error,error);self.assertEqual(len(self.process.signals),1)
        self.assertFalse(row['passed']);self.assertNotIn('listener',self.events);self.assertFalse(self.safety.completed)

    def test_diagnostics_incident_is_failure_even_after_safe_exit(self):
        self.diag_incident=RuntimeError('bounded capture full');row=self.run_worker()
        self.assertFalse(row['passed']);self.assertIs(self.run.first_error,self.diag_incident)
        self.assertEqual(len(self.process.signals),1);self.assertNotIn('listener',self.events)

    def test_live_owner_is_retained_without_closing_pipes(self):
        self.process.exit_on_signal=False;self.safety.fail_after_ready=RuntimeError('fault')
        row=self.run_worker();self.assertTrue(row['retained']);self.assertFalse(self.process.stdout.closed)
        self.assertEqual(len(self.process.signals),1);self.assertFalse(self.safety.released)

    def test_deterministic_launch_refusal_is_not_unknown_spawn(self):
        with patch.object(W,'native_placement',side_effect=RuntimeError('wrong placement')):row=self.run_worker()
        self.assertFalse(row['retained']);self.assertFalse(self.run.spawn_uncertain)
        self.assertEqual(self.popen_calls,[]);self.assertEqual(row['native_process_count'],0)

    def test_partial_acquire_never_completes_or_launches(self):
        self.safety.acquire_error=RuntimeError('partial acquisition')
        row=self.run_worker();self.assertFalse(row['passed']);self.assertFalse(row['retained'])
        self.assertEqual(self.popen_calls,[]);self.assertFalse(self.safety.completed);self.assertTrue(self.safety.released)

    def test_precompletion_write_failure_retains_coordination(self):
        append=W.BoundedEvidence.append
        error=OSError('precompletion fsync failed')
        def fail(writer,name,data):
            if name=='pre-completion.json':writer._fail(error);raise error
            return append(writer,name,data)
        with patch.object(W.BoundedEvidence,'append',side_effect=None,autospec=True) as mocked:
            mocked.side_effect=fail;row=self.run_worker()
        self.assertTrue(row['retained']);self.assertFalse(self.safety.completed);self.assertFalse(self.safety.released)
        self.assertIs(self.run.first_error,error)
        self.assertIn('terminal-evidence-failed',(self.root/'output/control/events.jsonl').read_text())

    def test_completion_guard_can_append_before_control_close(self):
        def completion_guard():self.run.control.append('kernel.jsonl',b'late clean kernel line\n')
        self.safety.on_complete=completion_guard
        row=self.run_worker();self.assertTrue(row['passed'])
        pre=json.loads((self.root/'output/terminal/pre-completion.json').read_text())
        self.assertFalse(pre['coordination_completed']);self.assertFalse(pre['passed'])
        self.assertTrue(pre['ready_for_coordination_completion'])
        self.assertIn('late clean',(self.root/'output/control/kernel.jsonl').read_text())

    def test_final_ack_failure_does_not_invent_retained_markers(self):
        append=W.BoundedEvidence.append;error=OSError('final ack fsync failed')
        def fail(writer,name,data):
            if name=='worker.json':writer._fail(error);raise error
            return append(writer,name,data)
        with patch.object(W.BoundedEvidence,'append',autospec=True,side_effect=fail):row=self.run_worker()
        self.assertFalse(row['passed']);self.assertFalse(row['retained'])
        self.assertTrue(row['coordination_completed']);self.assertTrue(row['post_completion_evidence_failure'])
        self.assertTrue(self.safety.completed);self.assertTrue(self.safety.released)
        self.assertTrue((self.root/'output/terminal/pre-completion.json').stat().st_size)

    def test_stopped_count_and_model_load_mismatch_refuse(self):
        self.stop_count_delta=1;row=self.run_worker();self.assertFalse(row['passed']);self.assertFalse(self.safety.completed)

    def test_boolean_model_load_is_not_one_load(self):
        self.model_loads=True;row=self.run_worker();self.assertFalse(row['passed']);self.assertNotIn('listener',self.events)

    def test_provenance_contradiction_does_not_fallback_or_listen(self):
        error=RuntimeError('wrong mapped clock');self.plan['activity_mode']='mapped-cold-start'
        prepared=types.SimpleNamespace(prove=lambda *a,**kw: (_ for _ in ()).throw(error))
        module=types.SimpleNamespace(prepare_owner_origin=lambda *a:prepared,__file__=str(W.INTEGRATION/'owner_idle_provenance.py'))
        with patch.dict(W.sys.modules,{'owner_idle_provenance':module}):row=self.run_worker()
        self.assertFalse(row['passed']);self.assertIs(self.run.first_error,error);self.assertNotIn('listener',self.events)
        self.assertEqual(len(self.process.signals),1)


class PlanTests(unittest.TestCase):
    def test_exact_real_plan_argv_intercepted_before_execution(self):
        with tempfile.TemporaryDirectory(dir=HERE,prefix='cpu-argv-') as parent:
            plan=W.cpu_plan(Path(parent));seen=[]
            class Intercept(Exception):pass
            def intercept(argv,**kwargs):seen.append((argv,kwargs));raise Intercept()
            with patch.object(W,'native_placement'),patch.object(W.subprocess,'Popen',side_effect=intercept):
                with self.assertRaises(Intercept):W.start_owner(plan['profile'],{'OMP_NUM_THREADS':'2','FilterBdfPath':'0000:23:00.0'})
            self.assertEqual(seen[0][0],plan['profile']['native_argv'])
            self.assertEqual(seen[0][1]['stderr'],subprocess.PIPE);self.assertEqual(len(seen),1)
            self.assertEqual(list(Path(parent).iterdir()),[])

    def test_finite_as_and_wrong_placement_refuse_before_spawn_boundary(self):
        profile={'native_argv':['/synthetic/never-executed']};env={'OMP_NUM_THREADS':'2','FilterBdfPath':'0000:23:00.0'}
        attempted=[]
        with (patch.object(W.os,'sched_getaffinity',return_value=W.MAIN_CORES),
              patch.object(W.os,'getpriority',return_value=0),
              patch.object(W.resource,'getrlimit',return_value=(4*1024**3,4*1024**3)),
              patch.object(W.subprocess,'Popen',side_effect=AssertionError('no spawn'))):
            with self.assertRaisesRegex(RuntimeError,'finite address-space'):W.start_owner(profile,env,before_spawn=lambda:attempted.append(True))
        with (patch.object(W.os,'sched_getaffinity',return_value=W.HELPER_CORES),
              patch.object(W.subprocess,'Popen',side_effect=AssertionError('no spawn'))):
            with self.assertRaisesRegex(RuntimeError,'nice0/main cores'):W.start_owner(profile,env,before_spawn=lambda:attempted.append(True))
        self.assertEqual(attempted,[])

    def test_real_safety_constructor_imports_only_pinned_helpers(self):
        with tempfile.TemporaryDirectory(dir=HERE,prefix='cpu-safety-') as parent:
            plan=W.cpu_plan(Path(parent))
            with (patch.object(W.subprocess,'run',side_effect=AssertionError('no operational read')),
                  patch.object(W.subprocess,'Popen',side_effect=AssertionError('no native'))):
                safety=W.Safety(plan,Path(parent)/'review-pending')
            self.assertEqual(safety.parent.ONE,W.P.parent/'packet181-session-swap-v3/one-card')
            self.assertIsNone(safety.lease);self.assertIsNone(safety.permit)
            self.assertEqual(safety.monitor.owners,{})

    def test_namespace_collision_refuses_before_plan_or_launch(self):
        with patch.object(W.sys.modules['native_diagnostics'],'__file__','/tmp/ambient.py'):
            with self.assertRaisesRegex(RuntimeError,'namespace collision'):W.cpu_plan(W.P)

    def test_fault_slice_is_preserved_before_guard_refuses(self):
        with tempfile.TemporaryDirectory(dir=HERE,prefix='cpu-fault-') as parent:
            safety=object.__new__(W.Safety);safety.output=Path(parent);safety.cursor='before'
            safety.parent=types.SimpleNamespace(QUEUE=Path(parent)/'queue',journal=lambda cursor:('raw GPU fault\n','after'))
            safety.m={'fault_review':types.SimpleNamespace(fault_lines=lambda text:['raw GPU fault'])}
            seen=[];run=types.SimpleNamespace(profile={'limits':{}},record={},control=types.SimpleNamespace(append=lambda name,data:seen.append(data)))
            with self.assertRaisesRegex(RuntimeError,'new kernel fault'):safety.check(run)
            self.assertEqual(seen,[b'raw GPU fault\n']);self.assertEqual(run.record['fault_cursor'],'after')

    def test_readonly_real_profile_plan_and_missing_manifest_refusal(self):
        with tempfile.TemporaryDirectory(dir=HERE,prefix='cpu-plan-') as parent:
            plan=W.cpu_plan(Path(parent));self.assertFalse(plan['live_admission_ready'])
            self.assertFalse(plan['storage_bound_proven']);self.assertEqual(plan['profile']['limits']['requests'],16)
            self.assertEqual(list(Path(parent).iterdir()),[])
            with patch.object(W.subprocess,'Popen',side_effect=AssertionError('must not launch')):
                with self.assertRaises(FileNotFoundError):W.execute(plan,fault_review=Path(parent)/'absent-review')


if __name__=='__main__':unittest.main()
