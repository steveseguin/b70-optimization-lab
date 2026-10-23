#!/usr/bin/env python3
"""One bounded interactive owner; CLI is read-only CPU planning only.

No live CLI/window is installed. execute() requires a future coordinator-owned
manifest and retains uncertain resources instead of unwinding borrowed leases.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import sys
import threading
import time

sys.dont_write_bytecode = True
P = Path(__file__).resolve().parent
ROOT = P.parents[3]
INTEGRATION = P.parents[1] / 'integration'
P199 = P.parent / 'packet199-chat-parking'
UNIT = 'packet200-bounded-serving-a'
MANIFEST = P / 'READY-FOR-DEVICE.json'
MAIN_CORES = {0, 1, 2, 3, 16, 17, 18, 19}
HELPER_CORES = set(range(8, 16)) | set(range(24, 32))
MIB = 1024**2
if str(INTEGRATION) not in sys.path:
    sys.path.insert(0, str(INTEGRATION))
import bounded_serving_profile as profile_module
import bounded_serving_session as session_module
from bounded_evidence import BoundedEvidence
from native_diagnostics import PipeDiagnostics
from native_checkpoint_store import NativeCheckpointStore
from request_front.client_v2 import NativeFront


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(path):
    with Path(path).open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def digest(row):
    return hashlib.sha256(json.dumps(row, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def integration_origins():
    for name in ('bounded_serving_profile','bounded_serving_session','bounded_evidence','native_diagnostics',
                 'native_checkpoint_store','request_front.client_v2'):
        module=sys.modules.get(name)
        require(module is not None and Path(getattr(module,'__file__','')).resolve()==INTEGRATION/(name.replace('.','/')+'.py'),
                'integration namespace collision: '+name)


def cpu_plan(staging_parent, *, activity_mode='launch'):
    integration_origins()
    parent = Path(staging_parent)
    require(activity_mode in ('launch', 'mapped-cold-start'), 'registered activity mode required')
    profile = profile_module.build_profile(parent / 'output', parent / 'checkpoints')
    return dict(schema='packet200.bounded-serving-plan.v1', passed=True, device_executed=False,
        live_admission_ready=False, storage_admission_mode='monitored-forecast', storage_bound_proven=False,
        unit=UNIT, profile=profile, profile_sha256=digest(profile), activity_mode=activity_mode,
        terminal_receipt=str(parent/'output/terminal/worker.json'), bind_host='127.0.0.1', bind_port=0,
        stderr_capture_bytes=8*MIB, control_evidence_bytes=7*MIB, terminal_evidence_bytes=MIB,
        native_processes=1, native_cpu_affinity=sorted(MAIN_CORES), native_nice=0,
        helper_cpu_affinity=sorted(HELPER_CORES), helper_nice=19,
        source_sha256={str((P/name).relative_to(ROOT)):sha(P/name) for name in
                       ('device_worker.py', 'test_device_worker.py', 'README.md')})


def authorize(plan, manifest):
    integration_origins()
    require(Path(manifest) == MANIFEST, 'fixed future coordinator manifest required')
    row = json.loads(MANIFEST.read_text())
    require(row.get('schema') == 'packet200.execution-admission.v1' and row.get('passed') is True
            and row.get('operational_launch_authorized') is True and row.get('plan_sha256') == digest(plan),
            'separate operational admission absent or changed')
    require(row.get('storage_admission_mode') == 'monitored-forecast' and row.get('storage_bound_proven') is False,
            'forecast must not become a hard-bound claim')
    expected = dict(plan['profile']['source_sha256']); expected.update(plan['source_sha256'])
    for name in ('native_diagnostics.py','initial_idle_origin.py'):
        expected[str((INTEGRATION/name).relative_to(ROOT))] = sha(INTEGRATION/name)
    if plan['activity_mode'] == 'mapped-cold-start':
        expected[str((INTEGRATION/'owner_idle_provenance.py').relative_to(ROOT))] = sha(INTEGRATION/'owner_idle_provenance.py')
    sealed = row.get('source_sha256', {})
    require(set(expected) <= set(sealed), 'new stack missing from execution closure')
    for path, value in sealed.items():
        require(sha(ROOT/path) == value and expected.get(path, value) == value, 'execution source drift: '+path)
    profile_module.validate_profile(plan['profile'])
    require(cpu_plan(Path(plan['profile']['paths']['output']).parent, activity_mode=plan['activity_mode']) == plan,
            'plan differs from fixed CPU derivation')


def helper_placement():
    tid = threading.get_native_id()
    os.setpriority(os.PRIO_PROCESS, tid, 19)
    os.sched_setaffinity(tid, HELPER_CORES)


def native_placement():
    require(os.sched_getaffinity(0) == MAIN_CORES and os.getpriority(os.PRIO_PROCESS, 0) == 0,
            'native launch requires unchanged nice0/main cores')
    require(resource.getrlimit(resource.RLIMIT_AS) == (resource.RLIM_INFINITY, resource.RLIM_INFINITY),
            'native refuses finite address-space limit')


def start_owner(profile, environment, *, before_spawn=lambda:None):
    native_placement()
    require(environment.get('OMP_NUM_THREADS') == '2' and environment.get('FilterBdfPath') == '0000:23:00.0',
            'exact single-card environment required')
    before_spawn()  # Ownership becomes uncertain only at the actual Popen boundary.
    return subprocess.Popen(profile['native_argv'], env=environment, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)


class Safety:
    """Narrow pinned p199/p198 admission reuse; no historical execution wrapper."""
    def __init__(self, plan, fault_review):
        spec = importlib.util.spec_from_file_location('_p200_pinned_p199', P199/'device_worker.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        self.parent = module.parent(); self.m = module.parent_modules()
        self.plan, self.fault_review = plan, Path(fault_review)
        self.output = Path(plan['profile']['paths']['output'])
        self.monitor = self.m['chain_devices'].DeviceMonitor('A')
        self.lease = self.permit = None
        self.lease_entered=self.permit_entered=self.completion_attempted=self.completed=self.released=False
        self.cursor = None

    def preflight(self):
        self.m['conditions'].lane_gate('A'); self.m['exec_limits'].check(); native_placement()
        cp = subprocess.run(['/usr/bin/systemctl','--user','show',UNIT+'.service',
            '--property=Restart,SendSIGKILL,TimeoutStopUSec,KillMode,ExitType'], capture_output=True,text=True,timeout=15)
        props = dict(line.split('=',1) for line in cp.stdout.splitlines() if '=' in line)
        require(cp.returncode == 0 and props == dict(Restart='no',SendSIGKILL='no',TimeoutStopUSec='infinity',KillMode='process',ExitType='cgroup'),
                'safe nonrestarting worker unit required')
        require(any(line.endswith('/'+UNIT+'.service') for line in Path('/proc/self/cgroup').read_text().splitlines()), 'fixed unit required')
        limits=self.plan['profile']['limits'];self.parent.memory(limits['host_required_available_bytes']+limits['coordinator_margin_bytes'])
        require(shutil.disk_usage(ROOT).free-limits['planned_write_bytes']>=limits['disk_floor_bytes'],'prelaunch storage forecast refused')
        review, initial, fresh, self.cursor = self.parent.validate_review(self.fault_review)
        return initial+fresh

    def acquire(self, guard):
        self.lease=self.m['lane_admission'].Reservation('A',window='screen',timing_claim=True,check=guard)
        self.lease.__enter__();self.lease_entered=True; require(self.lease.scope=='whole-host','whole-host lease required; no performance claim')
        self.m['chain_devices'].admit_clients('whole-host');self.m['chain_devices'].topology_admit('A')
        self.permit=self.m['drain_gate'].DrainPermit(self.output,check=guard,reservation=self.lease.record)
        self.permit.__enter__();self.permit_entered=True

    def before_launch(self):
        limits=self.plan['profile']['limits']
        self.parent.memory(limits['host_required_available_bytes']+limits['coordinator_margin_bytes'])
        require(shutil.disk_usage(ROOT).free-limits['planned_write_bytes']>=limits['disk_floor_bytes'], 'immediate prelaunch forecast refused')

    def environment(self):
        return self.m['chain_devices'].private_home(self.m['native_env'].environment('A'), self.output/'driver-home')

    def store_environment(self):
        import launch_env
        require(Path(launch_env.__file__).resolve()==self.parent.ONE/'launch_env.py','loader namespace collision')
        return launch_env.environment()

    def register(self, child): self.monitor.register(child.pid)

    def check(self, run):
        limits=run.profile['limits']
        for path in (self.parent.QUEUE/'STOP-A',self.parent.QUEUE/'STOP-B',self.parent.QUEUE/'PAUSE-A',self.output/'STOP'):
            require(not os.path.lexists(path),'admission latch '+str(path))
        text,self.cursor=self.parent.journal(self.cursor)
        faults=self.m['fault_review'].fault_lines(text)
        if faults:
            run.record['fault_excerpt']='\n'.join(faults[:8])[:16384]
            run.record['fault_cursor']=str(self.cursor)[:512]
        if text:run.control.append('kernel.jsonl',text.encode())
        require(not faults,'new kernel fault')
        require(shutil.disk_usage(ROOT).free>=limits['disk_floor_bytes'],'root free below27GB floor')
        self.parent.memory(self.parent.VIRTUAL_FLOOR)
        if run.launched_at is not None: require(time.monotonic()<run.launched_at+limits['native_seconds'],'absolute worker deadline')
        if run.child is not None:
            self.monitor.poll(force=True)
            require(all(fd['pci']=='0000:23:00.0' for owner in self.monitor.owners.values() for fd in owner['fds']), 'owner escaped card0')
            self.m['chain_devices'].admit_clients('whole-host',owned=self.monitor.live_identities())
            if run.child.poll() is None:
                used=self.m['common'].SUPPORT.process_tree_anon(run.child.pid)['anonymous_bytes']
                require(used<self.parent.HOST_REQUIRED-self.parent.VIRTUAL_FLOOR-256*MIB,'owner anonymous memory threshold')

    def ready(self, child):
        self.monitor.poll(force=True);require(self.monitor.owners[child.pid]['seen'],'card0 owner unproven')

    def postflight(self):
        self.monitor.finish();self.m['chain_devices'].admit_clients('whole-host')

    def complete(self):
        require(self.lease_entered and self.permit_entered,'cannot complete partial admission')
        self.completion_attempted=True
        self.permit.complete();self.lease.complete(drained=True);self.completed=True

    def release(self):
        if self.permit is not None:self.permit.__exit__(None,None,None)
        if self.lease is not None:self.lease.__exit__(None,None,None)
        self.released=True


class OwnedRun:
    """Own all resources explicitly, including retained failure states."""
    def __init__(self, plan, safety):
        self.plan,self.profile,self.safety=plan,plan['profile'],safety
        self.child=self.front=self.store=self.session=self.diagnostics=None
        self.stderr_writer=self.control=self.terminal=None
        self.launched_at=None;self.first_error=None;self.signalled=False;self.spawn_uncertain=False
        self.owner_uncertain=False;self.diagnostics_started=False;self.secondary_errors=[];self._written=set();self._used=False
        self.startup_thread=self.monitor_thread=None;self.stop_monitor=threading.Event();self.lock=threading.RLock()
        self.record=dict(passed=False,runtime_passed=False,evidence_passed=False,owner_exited=False,
            diagnostics_finished=False,devices_drained=False,retained=False,model_loads=0,requests=0,controls=0,
            storage_admission_mode='monitored-forecast',storage_bound_proven=False,live_profile_ready=False,
            incident_sigterm_count=0,listener_exposed=False,native_process_count=0,plan_sha256=digest(plan),
            owner_returncode=None,store_closed=False,writers_closed=False,coordination_completed=False,
            precompletion_written=False,post_completion_evidence_failure=False)

    def incident(self, error):
        with self.lock:
            if self.first_error is None:self.first_error=error
            if self.session is not None:self.session.request_close()
            try:
                if self.child is not None and self.child.poll() is None and not self.signalled:
                    self.signalled=True;self.record['incident_sigterm_count']=1
                    self.child.send_signal(signal.SIGTERM)
            except BaseException as secondary:
                self.owner_uncertain=True
                self.secondary_errors.append(dict(type=type(secondary).__name__,message=str(secondary)[:1024]))

    def guard(self):
        with self.lock:
            if self.first_error is not None:raise self.first_error
            if self.diagnostics is not None and self.diagnostics.incident_event.is_set():
                raise self.diagnostics.error or RuntimeError('diagnostic incident')
            self.safety.check(self)

    def _setup(self):
        initial=self.safety.preflight()
        for key in ('output','checkpoint_root'):
            path=Path(self.profile['paths'][key]);require(not os.path.lexists(path),'fresh destinations required')
            path.mkdir(mode=0o700)
        output=Path(self.profile['paths']['output'])
        for name in ('stderr','control','terminal'):(output/name).mkdir(mode=0o700)
        self.stderr_writer=BoundedEvidence(output/'stderr',total_limit_bytes=8*MIB,max_files=1)
        self.stderr_writer.create('native.stderr.log',limit_bytes=8*MIB)
        self.control=BoundedEvidence(output/'control',total_limit_bytes=7*MIB,max_files=4)
        self.control.create('kernel.jsonl',limit_bytes=6*MIB);self.control.create('events.jsonl',limit_bytes=MIB)
        self.terminal=BoundedEvidence(output/'terminal',total_limit_bytes=MIB,max_files=3)
        self.terminal.create('pre-completion.json',limit_bytes=256*1024)
        self.terminal.create('worker.json',limit_bytes=384*1024);self.terminal.create('retained.json',limit_bytes=384*1024)
        self.control.append('kernel.jsonl',initial.encode());self.safety.acquire(self.guard)

    def _start_diagnostics(self):
        self.diagnostics=PipeDiagnostics(self.child.stderr.fileno(),self.stderr_writer,'native.stderr.log')
        result={}
        def start():
            try:helper_placement();self.diagnostics.start()
            except BaseException as error:result['error']=error
        self.startup_thread=threading.Thread(target=start,name='p200-diagnostics-start',daemon=False)
        self.startup_thread.start();self.startup_thread.join(5)
        require(not self.startup_thread.is_alive(),'diagnostic startup retained')
        if 'error' in result:raise result['error']
        self.diagnostics_started=True
        self.child.stderr.close()  # Successful duplicate owns exclusive reads now.

    def _monitor(self):
        try:
            helper_placement()
            while not self.stop_monitor.wait(1):self.guard()
        except BaseException as error:self.incident(error)

    def _activity(self, prepared):
        if prepared is None:return self.launched_at,dict(mode='launch',conservative=True)
        proof=prepared.prove(self.child,admitted_argv=self.profile['native_argv'],launch_monotonic=self.launched_at)
        require(proof.get('last_native_activity') is not None,'idle provenance did not establish activity')
        return proof['last_native_activity'],proof

    def run(self):
        require(not self._used,'owner ledger is single use');self._used=True
        try:
            self._setup();env=self.safety.environment();prepared=None
            if self.plan['activity_mode']=='mapped-cold-start':
                from owner_idle_provenance import prepare_owner_origin
                require(Path(sys.modules['owner_idle_provenance'].__file__).resolve()==INTEGRATION/'owner_idle_provenance.py', 'idle provenance namespace collision')
                prepared=prepare_owner_origin(Path(self.profile['paths']['owner_output']),env)
            self.guard();self.safety.before_launch()
            def before_spawn():
                self.launched_at=time.monotonic();self.spawn_uncertain=True
            self.child=start_owner(self.profile,env,before_spawn=before_spawn)
            self.spawn_uncertain=False;self.record['native_process_count']=1
            self._start_diagnostics()  # No readiness wait or file scan before stderr drain.
            self.safety.register(self.child)
            self.monitor_thread=threading.Thread(target=self._monitor,name='p200-passive-guard',daemon=False)
            self.monitor_thread.start()
            self.front=NativeFront(self.child,context=4096,vocab=248320,max_requests=16,startup_timeout=900,request_timeout=900)
            self.record['model_loads']=self.front.ready['model_loads']
            require(type(self.record['model_loads']) is int and self.record['model_loads']==1,'exactly one model load required')
            self.safety.ready(self.child);self.guard()
            activity,proof=self._activity(prepared);self.record['initial_activity']=proof
            now=time.monotonic();limits=self.profile['limits']
            if now>=activity+limits['idle_seconds'] or now>=self.launched_at+limits['absolute_seconds']:
                self.guard();stopped=self.front.close(timeout=120);self.guard()
                self.record['unexposed_reason']='initial soft admission expired'
            else:
                self.store=NativeCheckpointStore(Path(self.profile['paths']['checkpoint_root']),Path(self.profile['binary']['path']),
                    self.profile['binary']['sha256'],self.safety.store_environment())
                self.session=session_module.attach(self.profile,front=self.front,store=self.store,
                    admitted_argv=self.profile['native_argv'],launched_at=self.launched_at,last_native_activity=activity,guard=self.guard)
                self.guard();address=self.session.open_listener(('127.0.0.1',0))
                self.record.update(listener_exposed=True,address=list(address))
                self.control.append('events.jsonl',(json.dumps(dict(event='listener',address=list(address)))+'\n').encode())
                terminal=self.session.serve();require(terminal['passed'] is True,'session terminal failed')
                stopped=terminal['lifecycle']['native_stopped'];self.record['session']=terminal
            require(stopped['safe_to_exit'] is True and stopped['discarded_pending'] is False
                    and stopped['pending_request_id']=='' and stopped.get('reason') in ('quit','request-limit','idle-timeout','deadline')
                    and type(self.front.completed) is int and type(self.front.completed_controls) is int
                    and 0<=self.front.completed==self.front.completed_controls<=16
                    and type(stopped.get('completed_requests')) is int and type(stopped.get('completed_controls')) is int
                    and stopped['completed_requests']==self.front.completed and stopped['completed_controls']==self.front.completed_controls,
                    'terminal count/disposition mismatch')
            require(self.child.poll()==0,'native owner did not exit0')
            self.record.update(runtime_passed=True,owner_exited=True,requests=self.front.completed,
                               controls=self.front.completed_controls,stopped=stopped)
            self.guard()
        except BaseException as error:
            self.incident(error)
        try:return self.finish()
        except BaseException as error:
            self.incident(error);self.record.update(passed=False,retained=True)
            self._capture_failure();return self.record

    def retained(self):
        diagnostic={} if self.diagnostics is None else self.diagnostics.status()
        return (self.spawn_uncertain or self.owner_uncertain
                or (self.child is not None and not self.diagnostics_started)
                or (self.child is not None and self.child.poll() is None)
                or bool(diagnostic.get('retained'))
                or any(thread is not None and thread.is_alive() for thread in (self.startup_thread,self.monitor_thread)))

    def _close_borrowed(self):
        if self.store is not None:self.store.close()
        self.record['store_closed']=True
        if self.child is not None:
            for pipe in (self.child.stdin,self.child.stdout,self.child.stderr):
                if pipe is not None and not pipe.closed:pipe.close()
        if self.stderr_writer is not None:self.stderr_writer.close()

    def finish(self):
        self.stop_monitor.set()
        if self.monitor_thread is not None and self.monitor_thread.ident is not None:self.monitor_thread.join(20)
        if self.child is not None and self.child.poll() is None:
            try:self.child.wait(timeout=65)
            except subprocess.TimeoutExpired:pass
        status={} if self.diagnostics is None else self.diagnostics.status()
        if status.get('started'):status=self.diagnostics.join(5)
        self.record['diagnostics']=status
        if status.get('incident'):self.incident(self.diagnostics.error or RuntimeError('diagnostic incident'))
        self.record['owner_returncode']=None if self.child is None else self.child.poll()
        self.record['owner_exited']=self.child is not None and self.record['owner_returncode'] is not None
        self.record['diagnostics_finished']=bool(status.get('eof')) and not status.get('retained',True)
        self.record['retained']=bool(self.retained())
        if self.record['retained']:
            self._capture_failure();return self.record
        try:
            if self.first_error is None:
                require(self.record['diagnostics_finished'],'diagnostic EOF not proven')
                self.guard();self.safety.postflight();self.guard();self.record['devices_drained']=True
                native=json.loads((Path(self.profile['paths']['owner_output'])/'receipt.json').read_text())
                require(native.get('passed') is True and native.get('safe_to_exit') is True and native.get('device_executed') is True,
                        'native physical shutdown receipt missing')
            self._close_borrowed()
            if self.first_error is None:
                # Durable physical/resource proof BEFORE removing coordination
                # markers. The control writer remains open for lease guard calls.
                self.record['ready_for_coordination_completion']=True
                self._terminal_record('pre-completion.json')
                self.record['precompletion_written']=True
                self.safety.complete();self.record['coordination_completed']=True
            if self.control is not None:self.control.close()
            self.record['writers_closed']=True  # stderr/control; terminal closes after final append.
            self.record['evidence_passed']=self.first_error is None
            self.record['passed']=self.first_error is None and self.record['runtime_passed'] and self.record['devices_drained']
            if self.first_error is None:
                self.safety.release()
                self._terminal_record('worker.json')
            else:
                self.record['error']=self._error_row()
                self._terminal_record('worker.json')  # Preserve failed run before releasing incomplete locks.
                self.safety.release()
            if self.terminal is not None:self.terminal.close()
        except BaseException as error:
            self.incident(error);self.record.update(passed=False,evidence_passed=False)
            if self.record['coordination_completed']:
                # Physical completion already happened. Do not claim its markers
                # are retained merely because the final acknowledgment failed.
                self.record['post_completion_evidence_failure']=True
                self.record['retained']=bool(self.retained())
                try:
                    if self.control is not None:self.control.close()
                    if self.terminal is not None:self.terminal.close()
                    self.safety.release()
                except BaseException as cleanup:
                    self.secondary_errors.append(dict(type=type(cleanup).__name__,message=str(cleanup)[:1024]))
                    self.record['retained']=True
            else:
                self.record['retained']=True
            self._capture_failure()
        return self.record

    def _error_row(self):
        error=self.first_error
        return None if error is None else dict(type=type(error).__name__,message=str(error)[:4096])

    def _capture_failure(self):
        self.record['error']=self._error_row()
        self.record['secondary_errors']=list(self.secondary_errors)
        try:self._terminal_record('retained.json')
        except BaseException as evidence_error:
            # Independent control evidence can survive a poisoned terminal
            # writer. Never mask the original incident or reopen any writer.
            try:
                if self.control is not None:
                    row=dict(event='terminal-evidence-failed',original=self._error_row(),evidence_error=str(evidence_error)[:1024])
                    self.control.append('events.jsonl',(json.dumps(row)+'\n').encode())
            except BaseException:pass

    def _terminal_record(self, name):
        if self.terminal is not None:
            require(name not in self._written,'terminal artifact is write-once')
            raw=(json.dumps(self.record,allow_nan=False,separators=(',',':'))+'\n').encode()
            limit=256*1024 if name=='pre-completion.json' else 384*1024
            require(len(raw)<=limit,'terminal receipt too large')
            self.terminal.append(name,raw);self._written.add(name)

    def hold_retained(self):
        # Preserve all resources and durable markers. No retries, closes or new
        # requests. External coordinator inspects this explicit retained unit.
        while self.record.get('retained'):time.sleep(30)


class WorkerFailure(RuntimeError):
    def __init__(self, original, record):
        self.original,self.record=original,record
        super().__init__(type(original).__name__+': '+str(original)[:4096])


def execute(plan, *, fault_review, manifest=MANIFEST):
    authorize(plan,manifest)
    owned=OwnedRun(plan,Safety(plan,fault_review))
    handlers={number:signal.signal(number,lambda n,f:owned.incident(RuntimeError('worker signal '+str(n))))
              for number in (signal.SIGTERM,signal.SIGINT)}
    try:
        result=owned.run()
        if result['retained']:owned.hold_retained()
        if not result['passed']:
            raise WorkerFailure(owned.first_error or RuntimeError('worker refused; see receipt'),result) from None
        return 0
    finally:
        for number,handler in handlers.items():signal.signal(number,handler)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',action='store_true',required=True)
    parser.add_argument('--staging-parent',type=Path,required=True)
    parser.add_argument('--activity-mode',choices=['launch','mapped-cold-start'],default='launch')
    args=parser.parse_args();print(json.dumps(cpu_plan(args.staging_parent,activity_mode=args.activity_mode)))
    return 0


if __name__=='__main__':raise SystemExit(main())
