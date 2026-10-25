#!/usr/bin/env python3
"""One explicitly admitted portable target-only replay, never a service/retry loop.

Default: validate plan and immutable/local/build identities without GPU work.
Execution requires --run, a digest-bound admission and cooperative coordinator.
"""
import argparse
from datetime import datetime, timezone
import json
import mmap
import os
from pathlib import Path
import select
import signal
import socket
import struct
import subprocess
import threading
import time

try:
    from . import launch_plan as planner, observer
except ImportError:
    import launch_plan as planner
    import observer

SLOT=65536
SHARED=4*SLOT+4096+64
REQUEST=struct.Struct('<8i')
REPLY=struct.Struct('<8i4d')

def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    return planner.hash_file(path)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def save(path, value):
    with Path(path).open('x') as output:
        json.dump(value, output, indent=2)
        output.write('\n')


def option(argv, key):
    require(argv.count(key) == 1, f'exactly one {key} required')
    return argv[argv.index(key) + 1]


class Guard:
    def __init__(self, plan, admission, stop_fd):
        self.plan, self.stop_fd = plan, stop_fd
        if stop_fd is not None:
            os.fstat(stop_fd)
        self.signal_stop = threading.Event()
        self.deadline = time.monotonic() + plan['seconds']
        self.obs = observer.Backend(admission['observer_backend'],admission.get('observer_wrapper'),admission.get('observer_wrapper_sha256'))
        self.baseline = planner.checked_file(admission['baseline'], admission['baseline_sha256'], 32*1024**2)
        require(self.baseline.get('schema') == 'ownrt.portable-observation.v1', 'portable baseline schema')
        self.identities, self.stoppers, self.lock = {}, [], threading.Lock()
        self.tracked_processes = []
        self.failed, self.done = None, threading.Event()
        self.targets = {s['bdf']: self.obs.target_nodes(self.baseline, s['bdf']) for s in plan['stages']}
        self.initial_observation=self.obs.observe()
        self.validate(self.initial_observation, initial=True)
        self.thread = threading.Thread(target=self.watch, daemon=True)

    def fail(self, reason):
        with self.lock:
            if self.failed is None:
                self.failed = str(reason)
                for fd in self.stoppers:
                    try:
                        os.write(fd, b'!')
                    except OSError:
                        pass

    def check(self):
        if time.monotonic() >= self.deadline:
            self.fail('bounded driver lifetime expired')
        if self.signal_stop.is_set():
            self.fail('coordinator signal stop')
        if self.stop_fd is not None and select.select([self.stop_fd], [], [], 0)[0]:
            self.fail('external coordinator stop/EOF')
        if self.failed:
            raise RuntimeError(self.failed)

    def validate(self, row, initial=False):
        require(row.get('schema')=='ownrt.portable-observation.v1' and row.get('observer_euid')==0 and row.get('device_opened') is False,'complete privileged passive observer attestation')
        require(row['boot'] == self.baseline['boot'] and row['drm'] == self.baseline['drm'], 'boot/DRM changed')
        require(row['kernel']['faults'] == self.baseline['kernel']['faults'], 'kernel fault baseline changed')
        require(not row['inventory']['errors'] and not row['identity_races'], 'incomplete or identity-raced device holder inventory')
        require(row['memory']['MemAvailable'] >= self.plan['memory_start_bytes' if initial else 'memory_floor_bytes'], 'memory floor')
        require(row['root_free_bytes'] >= self.plan['root_floor_bytes'], 'root free floor')
        import shutil
        require(shutil.disk_usage(Path(self.plan['output']).parent).free >= self.plan['evidence_floor_bytes'], 'evidence free floor')
        with self.lock:
            for h in row['inventory']['holders']:
                node, pid = h['node'], h['pid']
                bdf = next((b for b, nodes in self.targets.items() if node in nodes), None)
                identity = (row['holders'].get(str(pid)) or {}).get('start_ticks')
                registered = self.identities.get(pid)
                if bdf is not None:
                    require(not initial and registered == (identity, bdf), 'foreign/wrong-stage/ambiguous GPU holder')
                if registered:
                    require(bdf == registered[1], 'stage opened non-target card')

    def watch(self):
        while not self.done.wait(3):
            try:
                self.check()
                row = self.obs.observe()
                with (Path(self.plan['output']) / 'observations.jsonl').open('a') as out:
                    out.write(json.dumps(row) + '\n')
                self.validate(row)
            except Exception as error:
                self.fail(error)
                return


class Stage:
    def __init__(self, spec, plan, guard):
        self.spec, self.guard, self.sequence, self.plan = spec, guard, 0, plan
        self.path = Path(plan['output']) / f"stage{spec['id']}"
        self.path.mkdir(mode=0o700)
        native_output = Path(spec['native_output'])
        require(native_output == self.path / 'native' and option(spec['argv'], '--output') == str(native_output), 'native output path identity')
        require(not os.path.lexists(native_output), 'native output must remain absent until engine creates it')
        self.file = (self.path / 'shared.bin').open('x+b')
        self.file.truncate(SHARED)
        self.shared = mmap.mmap(self.file.fileno(), SHARED)
        self.sock, child = socket.socketpair()
        self.sock.settimeout(0.2)
        read_stop, write_stop = os.pipe()
        argv = [str(child.fileno()) if x == '<channel-fd>' else str(read_stop) if x == '<stop-fd>' else x for x in spec['argv']]
        self.log = (self.path / 'process.log').open('xb')
        try:
            with guard.lock:
                guard.stoppers.append(write_stop)
                # Recheck admission atomically with registration: the observer may
                # have stopped work after execute()'s previous check. Do not call
                # check()/fail() under this nonrecursive lock.
                require(guard.failed is None and not guard.signal_stop.is_set() and time.monotonic() < guard.deadline, 'stage launch cancelled before Popen')
                require(guard.stop_fd is None or not select.select([guard.stop_fd], [], [], 0)[0], 'external stop before Popen')
                self.proc = subprocess.Popen(argv, env=spec['environment'], stdin=subprocess.DEVNULL, stdout=self.log, stderr=subprocess.STDOUT, pass_fds=(child.fileno(), read_stop))
                # Retain ownership before identity capture or evidence writes can
                # fail. Every spawned child participates in cooperative teardown.
                guard.tracked_processes.append((spec['id'], self.proc))
                identity = guard.obs.process_identity(self.proc.pid)
                require(identity is not None, 'stage PID identity absent')
                guard.identities[self.proc.pid] = (identity['start_ticks'], spec['bdf'])
        finally:
            child.close()
            os.close(read_stop)
        save(self.path / 'launch.json', dict(argv=argv, environment=spec['environment'], pid=self.proc.pid, identity=identity))
        self.stream_bytes = None

    def receive(self, ready=False):
        data, end = bytearray(), time.monotonic() + self.plan['seconds']
        while len(data) < REPLY.size:
            self.guard.check()
            require(time.monotonic() < end, 'bounded stage reply timeout')
            try:
                piece = self.sock.recv(REPLY.size - len(data))
            except socket.timeout:
                continue
            require(piece, 'stage channel closed')
            data.extend(piece)
        r = REPLY.unpack(data)
        require(r[0] == 0 and r[2] == 0 and r[4] == self.sequence, 'stage error/sequence')
        require(r[5] == (0 if self.spec['first'] else 1) and r[6:8] == (self.spec['id'], int(self.spec['final'])), 'reply stage/final identity')
        if ready:
            require(0 < r[3] <= SLOT and r[3] % 4 == 0, 'F32 ready stream extent')
            self.stream_bytes = r[3]
        return r

    def command(self, op, token=0, position=0, fixture=0):
        self.guard.check()
        self.sequence += 1
        self.sock.sendall(REQUEST.pack(op, token, position, fixture, 0, self.sequence, self.spec['id'], int(self.spec['final'])))
        return None if op == 5 else self.receive()


def validate_unit(unit):
    invocation = os.environ.get('INVOCATION_ID')
    require(unit and invocation, 'run without external FD requires a named systemd unit')
    result = subprocess.run(['systemctl', '--user', 'show', unit, '--property=MainPID,InvocationID,Restart,KillMode,SendSIGKILL'], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=10)
    require(result.returncode == 0 and not result.stderr.strip(), 'unit policy observation failed')
    fields = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    require(fields.get('InvocationID') == invocation and fields.get('MainPID') == str(os.getpid()), 'unit/driver ownership identity')
    require(fields.get('Restart') == 'no' and fields.get('KillMode') == 'process' and fields.get('SendSIGKILL') == 'no', 'unit must forbid restart and forced child teardown')
    return fields


def execute(plan, admission, stop_fd=None, unit=None):
    require(admission.get('schema') == 'ownrt.portable-run-admission.v1' and admission.get('owner_authorized') is True, 'explicit admission required')
    require(datetime.fromisoformat(admission['expires_utc']) > datetime.now(timezone.utc), 'admission expired')
    require(os.getpriority(os.PRIO_PROCESS, 0) == 19, 'launch driver under nice -n 19')
    unit_identity = validate_unit(unit) if stop_fd is None else None
    output = Path(plan['output'])
    guard = Guard(plan, admission, stop_fd)
    prior_handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    for sig in prior_handlers:
        signal.signal(sig, lambda *_: guard.signal_stop.set())
    output.mkdir(mode=0o700)
    save(output / 'plan.json', plan)
    save(output / 'admission.json', admission)
    save(output / 'baseline.json',guard.baseline)
    save(output / 'preflight.json',guard.initial_observation)
    if unit_identity is not None:
        save(output / 'unit.json', unit_identity)
    stages, emitted, failure = [], [], None
    started = time.monotonic()
    try:
        guard.thread.start()
        # One load per stage; readiness is checked before admitting token work.
        for spec in plan['stages']:
            guard.check()
            stage = Stage(spec, plan, guard)
            stages.append(stage)
            stage.receive(ready=True)
        require(len({s.stream_bytes for s in stages}) == 1, 'stage stream extents differ')
        guard.validate(guard.obs.observe())
        position, fixture = 0, 0
        token = plan['prompt_tokens'][0]
        with (output / 'tokens.jsonl').open('x') as token_log:
            while True:
                guard.check()
                is_prompt = position < len(plan['prompt_tokens'])
                if is_prompt:
                    token = plan['prompt_tokens'][position]
                fixture = max(0, position - len(plan['prompt_tokens']) + 2)
                step_start = time.monotonic()
                stage_times = []
                for i, stage in enumerate(stages):
                    if i:
                        stage.shared[SLOT:SLOT + stage.stream_bytes] = stages[i-1].shared[:stage.stream_bytes]
                    r = stage.command(1, token, position, fixture)
                    require((stage.spec['final'] and r[3] == 0) or (not stage.spec['final'] and r[3] == stage.stream_bytes and r[1] == -1), 'handoff bytes/token identity')
                    stage_times.append(r[8])
                    stage.command(2, token, position, fixture)
                position += 1
                if fixture:
                    token = r[1]
                    require(0 <= token < plan['vocab'], 'final token bounds')
                    emitted.append(token)
                    token_log.write(json.dumps(dict(position=position, token=token, elapsed_ms=(time.monotonic()-step_start)*1000, stage_ms=stage_times)) + '\n')
                    token_log.flush()
                    if len(emitted) >= plan['max_new'] or token in plan['eos_token_ids']:
                        break
        for stage in stages:
            stage.command(4, position=2147483647)
        guard.validate(guard.obs.observe())
        for stage in stages:
            stage.command(5)
    except Exception as error:
        failure = repr(error)
        guard.fail(failure)
    finally:
        deadline = time.monotonic() + plan['grace_seconds']
        while any(proc.poll() is None for _, proc in guard.tracked_processes) and time.monotonic() < deadline:
            time.sleep(0.2)
        guard.done.set()
        guard.thread.join(timeout=40)
        if guard.thread.is_alive():
            guard.fail('passive monitor did not quiesce')
        try:
            postflight=guard.obs.observe()
            save(output/'postflight.json',postflight)
            guard.validate(postflight)
            guard.check()
        except Exception as error:
            guard.fail(error)
        failure = failure or guard.failed
        # Never kill, restart, reset a driver or mutate host settings.
        alive = [proc.pid for _, proc in guard.tracked_processes if proc.poll() is None]
        codes = {str(stage_id): proc.poll() for stage_id, proc in guard.tracked_processes}
        if alive or any(rc != 0 for rc in codes.values()):
            failure = failure or 'stage failed to exit cleanly'
        for sig, handler in prior_handlers.items():
            signal.signal(sig, handler)
        save(output / 'result.json', dict(passed=failure is None, error=failure, live_pids=alive, returncodes=codes, output_ids=emitted, wall_seconds=time.monotonic()-started, mode='target-only', speed_claim=False, input_position=locals().get('position', 0)))
    require(failure is None, str(failure))
    return output / 'result.json'


def verify_plan(path, plan_sha, profile_sha, binding_sha, receipt_path, receipt_sha):
    plan=planner.checked_file(path,plan_sha,8*1024**2)
    require(plan.get('schema')=='ownrt.portable-launch-plan.v1' and plan.get('mode')=='target-only', 'portable target-only plan required; MTP controller is separate')
    require(plan.get('model_profile_sha256')==profile_sha and plan.get('deployment_binding_sha256')==binding_sha,'independent model/binding digest mismatch')
    require(plan.get('pins',{}).get(str(Path(receipt_path).absolute()))==receipt_sha,'independent build receipt digest mismatch')
    stages=plan['stages']
    require(len(stages) in (2,4),'two/four stage proof only')
    deployment=Path(option(stages[0]['argv'],'--plan')).parent
    expected=planner.make_plan(deployment,profile_sha,binding_sha,receipt_path,receipt_sha,
        [s['bdf'] for s in stages],stages[0]['environment']['LD_LIBRARY_PATH'].split(':'),
        plan['output'],plan['prompt_tokens'],plan['mode'],plan['max_new'],plan['seconds'],
        policy_path=plan['launch_policy']['path'],policy_sha256=plan['launch_policy']['sha256'])
    actual_pins=plan['pins'];expected_pins=expected['pins']
    require(all(actual_pins.get(p)==sha for p,sha in expected_pins.items()),'missing/changed regenerated plan pins')
    for p,sha in actual_pins.items():require(digest(p)==sha,'pinned launch artifact changed: '+p)
    expected['pins']=actual_pins
    require(plan==expected,'launch commands/environment/geometry differ from trusted generator')
    return plan


def admit(plan, admission, plan_sha):
    require(admission.get('schema')=='ownrt.portable-run-admission.v1' and admission.get('owner_authorized') is True,'explicit run admission required')
    require(admission.get('plan_sha256')==plan_sha,'admission plan digest mismatch')
    require(admission.get('controller_sha256')==digest(__file__) and
            admission.get('observer_sha256')==digest(observer.__file__),'controller/observer code identity')
    require(admission.get('observer_backend') in ('direct-root','sudo-n','external-wrapper'),'explicit complete-inventory observer backend')
    if admission['observer_backend']=='external-wrapper':
        observer.Backend('external-wrapper',admission.get('observer_wrapper'),admission.get('observer_wrapper_sha256'))
    expiry=datetime.fromisoformat(admission['expires_utc'])
    require(expiry.tzinfo is not None and datetime.now(timezone.utc)<expiry,'run admission expired or timezone absent')
    limits=admission['limits']
    for name in ('memory_start_bytes','memory_floor_bytes','root_floor_bytes','evidence_floor_bytes','grace_seconds'):
        require(type(limits.get(name)) is int,'integer resource limit '+name)
    require(limits['memory_start_bytes']>=limits['memory_floor_bytes']>=8*1024**3,'memory floors')
    require(limits['root_floor_bytes']>=1024**3 and limits['evidence_floor_bytes']>=2*1024**3,'storage floors')
    require(10<=limits['grace_seconds']<=600,'bounded cooperative stop grace')
    require(not set(limits)-{'memory_start_bytes','memory_floor_bytes','root_floor_bytes','evidence_floor_bytes','grace_seconds'},'unknown admission limit')
    return dict(plan,**limits)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--plan-sha256',required=True)
    p.add_argument('--profile-sha256',required=True)
    p.add_argument('--binding-sha256',required=True)
    p.add_argument('--build-receipt',type=Path,required=True)
    p.add_argument('--build-receipt-sha256',required=True)
    p.add_argument('--run',action='store_true')
    p.add_argument('--admission',type=Path)
    p.add_argument('--coordinator-stop-fd',type=int)
    p.add_argument('--unit')
    a=p.parse_args()
    plan=verify_plan(a.plan,a.plan_sha256,a.profile_sha256,a.binding_sha256,a.build_receipt,a.build_receipt_sha256)
    if not a.run:
        print(json.dumps(dict(plan_validated=True,device_execution_requested=False,mode='target-only')))
        return
    require(a.admission is not None and (a.coordinator_stop_fd is not None or a.unit),'run requires admission and external stop FD or own no-restart unit')
    admission=json.loads(planner.prep.read_small(a.admission))
    execution_plan=admit(plan,admission,a.plan_sha256)
    print(execute(execution_plan,admission,a.coordinator_stop_fd,a.unit))


if __name__=='__main__':main()
