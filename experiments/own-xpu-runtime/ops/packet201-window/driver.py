#!/usr/bin/env python3
"""Single manually coordinated packet201 lifecycle window; no retry/resume path."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

sys.dont_write_bytecode = True
import importlib.util

def load(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module

_THIS=Path(__file__).resolve().parent
H=load('_p201_driver_helpers',_THIS/'helpers.py')
C=load('_p201_frozen_window_contract',_THIS/'window.py')
S = H.S
HERE, ROOT, QUEUE, UNIT = H.HERE, H.ROOT, S.QUEUE, S.UNIT
PACKET = C.PACKET
A = load('_p201_execution_adapter', PACKET/'run.py')
WORKER = PACKET/'run.py'
STAGE = A.STAGE
OUTPUT = STAGE/'output'
REVIEW = A.REVIEW
PYTHON = A.PYTHON
CHECKPOINT_ROOT = STAGE/'checkpoints'
CLIENT_UNIT='packet201-client-a'
CLIENT_SCRIPT=PACKET/'client_pilot.py'
CLIENT_RESULT=PACKET/'evidence/client-a/client-result.json'
EXPECTED_MANIFEST_SHA = None
RESTORE_SUFFIX = '20261023-restore30'


def admission():
    return A.verify_manifest(EXPECTED_MANIFEST_SHA)


def safe_stop(unit):
    row=S.require_safe_stop(unit)
    S.require(row.get('KillMode') == 'process', 'process-only endpoint stop required')
    return row


def clear():
    admission(); H.verify()
    S.faults_clear()
    S.require(not any(os.path.lexists(p) for p in (QUEUE / 'STOP-A', QUEUE / 'STOP-B', OUTPUT / 'STOP')),
              'incident latch present; no launch or restore')


def status(unit=UNIT):
    cp = S.command(['systemctl', '--user', 'show', unit + '.service',
                    '--property=LoadState,ActiveState,Result,ExecMainStatus,MainPID,Restart,SendSIGKILL,TimeoutStopUSec,KillMode'])
    S.require(cp.returncode == 0, 'worker unit status unreadable')
    return dict(line.split('=', 1) for line in cp.stdout.splitlines() if '=' in line)


def plan():
    admission()
    cp = S.command(S.PY[:6]+[PYTHON,'-B',WORKER,'--verify-admission'],timeout=1800)
    S.require(cp.returncode==0,'worker CPU plan refused: '+cp.stderr[-600:])
    row=json.loads(cp.stdout)
    C.validate_cpu_plan(row,STAGE)
    S.require(row['activity_mode']=='launch','first run uses launch-origin activity')
    manifest,_=admission()
    S.require(manifest['plan_sha256']==C.digest(row),'root manifest plan differs')
    return row


def restore_clear():
    clear()
    manifest,_=admission()
    evidence=Path(manifest['controller']['evidence'])
    for lane in ('A','B'):
        S.require((QUEUE/f'PAUSE-{lane}').read_bytes()==(evidence/f'PAUSE-{lane}.before').read_bytes(),
                  'pause changed before restoration operation')
        S.require(not S.read_rows(QUEUE/f'queue-{lane}.txt'),'queued work blocks restoration')


# The unchanged p196 imports this alias in the restore process only.
faults_clear=restore_clear


def check(suffix, evidence):
    manifest,manifest_sha=admission()
    H.verify()
    controller=manifest.get('controller',{})
    S.require(controller.get('restore_suffix')==suffix and controller.get('evidence')==str(evidence),
              'controller invocation differs from root admission')
    S.require(evidence.is_absolute() and evidence.resolve()==evidence and evidence.parent==HERE/'evidence',
              'fresh direct controller evidence child required')
    S.require(type(controller.get('additional_write_bytes')) is int and controller['additional_write_bytes']==1048576,
              'fixed additional client evidence reserve required')
    S.require(controller.get('client_unit')==CLIENT_UNIT and controller.get('client_receipt')==str(CLIENT_RESULT)
              and type(controller.get('qualification_requests')) is int and controller['qualification_requests']==16,
              'fixed sixteen-request client qualification required')
    stage=C.staging_identity(STAGE)
    S.require(controller.get('staging_identity')==stage,'root-admitted private staging identity differs')
    S.require(suffix == RESTORE_SUFFIX, 'fixed restore30 suffix required')
    S.require(not any(os.path.lexists(p) for p in (evidence, OUTPUT, REVIEW, REVIEW.with_suffix('.kernel.jsonl.gz'), CHECKPOINT_ROOT, PACKET/'evidence/client-a')),
              'fresh coordinator/worker/review/checkpoint paths required; never retry')
    for name in (suffix, 'qwen38-27b-fp8-card0-' + suffix, 'qwen38-27b-fp8-card3-' + suffix, 'qwen38-27b-vision-' + suffix):
        S.require(not (Path('/home/steve/inference') / name).exists(), 'restore destination already exists')
    S.require(shutil.disk_usage(ROOT).free >= 27_000_000_000, 'root free below 27 GB')
    registered = plan()
    S.require(shutil.disk_usage(ROOT).free >= registered['profile']['limits']['disk_floor_bytes'] +
              registered['profile']['limits']['planned_write_bytes'] + 1048576,
              'storage floor after planned writes refused before endpoint stop')
    clear(); S.no_owners()
    S.require(status().get('LoadState') == 'not-found', 'worker unit already exists; inspect, never reset')
    S.require(status(CLIENT_UNIT).get('LoadState') == 'not-found','client unit already exists; no retry')
    for lane in ('A', 'B'):
        S.require((QUEUE / f'PAUSE-{lane}').is_file() and not S.read_rows(QUEUE / f'queue-{lane}.txt'), 'both lanes must be paused with empty queues')
        backend, _ = S.backend(); backend.guards(lane)
    self_unit = next((line.rsplit('/', 1)[-1] for line in Path('/proc/self/cgroup').read_text().splitlines() if line.startswith('0::')), '')
    cp = S.command(['systemctl', '--user', 'list-units', 'lanequeue-*', 'window-*', 'packet*',
                    '--state=active,activating,deactivating,reloading', '--no-legend', '--plain'])
    busy = [line.split()[0] for line in cp.stdout.splitlines() if line.split() and line.split()[0] != self_unit]
    S.require(cp.returncode == 0 and not busy, 'another window active or discovery failed: ' + str(busy))
    endpoints = {}
    for unit in S.ENDPOINTS:
        endpoints[unit] = safe_stop(unit)
        S.require(endpoints[unit].get('ActiveState') == 'active', 'prior endpoint not active: ' + unit)
    S.endpoint_idle()
    return dict(at=S.now(), endpoints=endpoints, plan=registered, worker_sha256=S.sha(WORKER),
                manifest_sha256=manifest_sha, staging_identity=stage,
                boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip())


def terminal(plan_row, state, *, passive_drained):
    row=json.loads((OUTPUT/'terminal/worker.json').read_text())
    pre=json.loads((OUTPUT/'terminal/pre-completion.json').read_text())
    proof=C.validate_terminal(row,plan_sha256=C.digest(plan_row),unit_status=state,
                              passive_drained=passive_drained,precompletion=pre)
    return dict(worker=row,validation=proof,precompletion=pre)


def bounded_json(path,limit):
    with Path(path).open('rb') as file:raw=file.read(limit+1)
    S.require(len(raw)<=limit,'client evidence exceeds bound')
    return json.loads(raw),raw


def client_provenance():
    _,manifest_sha=admission()
    recorded,_=bounded_json(CLIENT_RESULT.parent/'admission.json',65536)
    S.require(recorded.get('manifest_sha256')==manifest_sha and
              recorded.get('vectors_sha256')==S.sha(PACKET/'client-vectors.json'),
              'client admission/source provenance differs')
    events=OUTPUT/'control/events.jsonl'
    with events.open('rb') as file:raw=file.read(1024*1024+1)
    S.require(len(raw)<=1024*1024 and recorded.get('listener_events_sha256')==hashlib.sha256(raw).hexdigest(),
              'client listener evidence differs')
    listeners=[r for line in raw.splitlines() if (r:=json.loads(line)).get('event')=='listener']
    S.require(len(listeners)==1 and recorded.get('address')==listeners[0].get('address'),
              'client listener address differs')
    return recorded


def client_terminal(state=None):
    state=status(CLIENT_UNIT) if state is None else state
    S.require(state.get('ActiveState')=='inactive' and state.get('Result')=='success' and state.get('ExecMainStatus')=='0',
              'client unit must exit successfully before qualification')
    client_provenance()
    row,_=bounded_json(CLIENT_RESULT,65536)
    expected=dict(passed=True,requests=16,exact_recorded_requests=5,resumed_fresh_pairs=1,
                  maximum_output_tokens=1728,output_tokens=1484,controls_claimed=False,submission_eligible=False,speed_claim=False,
                  p200_exact_requests=16,sse_requests=7,ordinary_requests=9,sse_terminal_sequences=7,
                  observed_delivery_timing_only=True)
    S.require(all(type(row.get(k)) is type(v) and row[k]==v for k,v in expected.items()),
              'client qualification counts/oracle/scope proof failed')
    S.require(type(row.get('output_tokens')) is int and 1<=row['output_tokens']<=1728,'client output token count outside cap')
    return row


def qualification(plan_row,state,*,passive_drained,client_state=None):
    result=terminal(plan_row,state,passive_drained=passive_drained)
    S.require(result['worker']['requests']==16 and result['worker']['controls']==16,
              'first serving qualification requires sixteen completed turns')
    result['client']=client_terminal(client_state)
    return result


class Window:
    def __init__(self, evidence, suffix):
        self.evidence, self.suffix = evidence, suffix
        self.pause = {}
        self.mutated = self.launched = self.signalled = False
        self.listener_announced=False
        self.client_launched=False

    def save(self, name, row):
        (self.evidence / name).write_text(json.dumps(row, indent=2) + '\n')

    def log(self, text):
        line = S.now() + ' ' + text
        print(line, flush=True)
        with (self.evidence / 'driver.log').open('a') as file: file.write(line + '\n')

    def rearm(self):
        if not (QUEUE / 'PAUSE-A').exists():
            with (QUEUE / 'PAUSE-A').open('xb') as file: file.write(self.pause['A'])
        for lane in ('A', 'B'):
            S.require((QUEUE / f'PAUSE-{lane}').read_bytes() == self.pause[lane], 'external pause change retained: ' + lane)

    def incident(self):
        try:
            self.rearm()
        except (OSError, RuntimeError) as error:
            self.log('external pause retained during incident: ' + str(error))
            self.save('incident-pause-refusal.json', dict(error=str(error), external_bytes_preserved=True))
        for path in (QUEUE / 'STOP-A', OUTPUT / 'STOP'):
            if not path.parent.exists(): continue
            try:
                with path.open('xb') as file: file.write(('packet201 incident ' + S.now() + '\n').encode())
            except FileExistsError: pass
        if self.launched and S.active(UNIT) and not self.signalled:
            safe_stop(UNIT); self.signalled = True
            cp = S.command(['systemctl', '--user', 'kill', '--kill-whom=main', '--signal=SIGTERM', UNIT + '.service'])
            self.save('cooperative-stop.json', dict(sent_once=True, rc=cp.returncode, stdout=cp.stdout, stderr=cp.stderr))
            S.require(cp.returncode == 0, 'main-process cooperative stop failed; no escalation')
        end = time.monotonic() + 900
        while self.launched and S.active(UNIT) and time.monotonic() < end: time.sleep(5)
        S.require(not self.launched or not S.active(UNIT), 'worker retained after drain deadline; no kill/restore')

    def start_client(self,event):
        S.require(not self.client_launched,'client launch already attempted; no retry')
        address=event.get('address')
        S.require(type(address) is list and len(address)==2 and address[0]=='127.0.0.1' and
                  type(address[1]) is int and 1<=address[1]<=65535,'fixed loopback listener event required')
        clear();admission()
        S.require(status(CLIENT_UNIT).get('LoadState')=='not-found','client unit already exists; no retry')
        argv=['systemd-run','--user','--unit='+CLIENT_UNIT,'--working-directory='+str(ROOT),*S.SAFE_PROPS,
              '--property=Nice=19','/usr/bin/taskset','-c','8-15,24-31',PYTHON,'-B',str(CLIENT_SCRIPT),'--execute']
        self.client_launched=True  # An ambiguous command failure is never retried.
        cp=S.command(argv)
        self.save('client-launch.json',dict(argv=argv,rc=cp.returncode,stdout=cp.stdout,stderr=cp.stderr))
        S.require(cp.returncode==0,'client launch refused; no retry')
        self.log('listener '+json.dumps(event,sort_keys=True)+'; one qualification client started')
        self.listener_announced=True

    def watch(self, plan_row):
        end=time.monotonic()+7500
        final_rechecks=0
        while time.monotonic()<end:
            clear()
            S.require(not (QUEUE/'PAUSE-A').exists() and (QUEUE/'PAUSE-B').read_bytes()==self.pause['B'],
                      'pause changed while worker active')
            state=status()
            if state.get('ActiveState') not in S.ACTIVE:
                S.require(state.get('ActiveState')=='inactive' and state.get('Result')=='success' and
                          state.get('ExecMainStatus')=='0','worker unit did not succeed')
                S.require(self.client_launched,'worker ended before qualification client started')
            if not self.client_launched:
                events=OUTPUT/'control/events.jsonl'
                if events.exists():
                    with events.open() as event_file:event_text=event_file.read(1024*1024+1)
                    S.require(len(event_text.encode())<=1024*1024,'listener evidence exceeds bound')
                    listeners=[]
                    for line in event_text.splitlines():
                        try:event=json.loads(line)
                        except json.JSONDecodeError:continue  # Last concurrent append may be partial.
                        if event.get('event')=='listener':listeners.append(event)
                    S.require(len(listeners)<=1,'multiple listener events refused')
                    if listeners:self.start_client(listeners[0])
            client_state=status(CLIENT_UNIT) if self.client_launched else None
            if client_state is not None and client_state.get('ActiveState') not in S.ACTIVE:
                S.require(client_state.get('ActiveState')=='inactive' and client_state.get('Result')=='success' and
                          client_state.get('ExecMainStatus')=='0','client unit did not succeed; no further requests')
                client_terminal(client_state)  # Refuse oracle failure even while worker is draining.
            if state.get('ActiveState')=='inactive' and client_state is not None and client_state.get('ActiveState')=='inactive':
                try:
                    drain=S.require_drained();self.save('terminal-passive-drain.json',drain)
                    result=qualification(plan_row,state,passive_drained=True,client_state=client_state)
                except (FileNotFoundError,json.JSONDecodeError):
                    final_rechecks+=1
                    S.require(final_rechecks<=2,'final worker receipt unavailable after exit')
                else:return result
            time.sleep(5)
        raise RuntimeError('worker/client watch deadline; no retry')

    def execute(self):
        global EXPECTED_MANIFEST_SHA
        pre = check(self.suffix, self.evidence)
        EXPECTED_MANIFEST_SHA=pre['manifest_sha256']
        self.evidence.mkdir()
        self.pause = {lane:(QUEUE / f'PAUSE-{lane}').read_bytes() for lane in ('A', 'B')}
        self.save('preflight.json', pre)
        for lane, data in self.pause.items(): (self.evidence / f'PAUSE-{lane}.before').write_bytes(data)
        failure = None
        try:
            clear(); S.endpoint_idle(); self.mutated = True
            self.log('stopping the three idle prior endpoints once')
            for unit in S.ENDPOINTS:
                clear(); safe_stop(unit)
                cp = S.command(['systemctl', '--user', 'stop', '--no-block', unit + '.service'])
                S.require(cp.returncode == 0, 'endpoint stop request failed')
            end = time.monotonic() + 600
            while any(S.active(u) for u in S.ENDPOINTS) and time.monotonic() < end:
                clear(); time.sleep(5)
            S.require(not any(S.active(u) for u in S.ENDPOINTS), 'endpoint drain deadline; no escalation')
            self.save('post-stop-drain.json', S.require_drained())
            C.require_same_staging_identity(pre['staging_identity'])
            registered = pre['plan']; fresh = plan()
            S.require(fresh == registered and S.sha(WORKER) == pre['worker_sha256'], 'worker plan/source changed during admission')
            available = next(int(line.split()[1]) * 1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
            S.require(available >= registered['profile']['limits']['host_required_available_bytes'] + registered['profile']['limits']['coordinator_margin_bytes'], 'host memory floor refused')
            S.require(shutil.disk_usage(ROOT).free >= registered['profile']['limits']['disk_floor_bytes'] + registered['profile']['limits']['planned_write_bytes'] + 1048576, 'storage floor refused')
            clear()
            cp = S.command(S.PY[:6] + [PYTHON,'-B',str(WORKER),'--capture-fault-review'], timeout=1800)
            self.save('fault-review-command.json', dict(rc=cp.returncode, stdout=cp.stdout, stderr=cp.stderr))
            S.require(cp.returncode == 0 and REVIEW.exists(), 'fresh fault review refused')
            clear()
            with S.locked(QUEUE / 'edit-A.lock'):
                S.require(not S.read_rows(QUEUE / 'queue-A.txt') and not S.read_rows(QUEUE / 'queue-B.txt'), 'queue changed during admission')
                S.require(all((QUEUE / f'PAUSE-{lane}').read_bytes() == data for lane,data in self.pause.items()), 'pause changed before launch')
                (QUEUE / 'PAUSE-A').unlink()
            clear(); self.launched = True
            argv = ['systemd-run', '--user', '--unit=' + UNIT, '--working-directory=' + str(ROOT), *S.SAFE_PROPS,
                    '--property=Nice=0', '/usr/bin/taskset', '-c', '0-3,16-19', *A.worker_argv()]
            cp = S.command(argv)
            self.save('worker-launch.json', dict(argv=argv, rc=cp.returncode, stdout=cp.stdout, stderr=cp.stderr))
            S.require(cp.returncode == 0, 'worker launch refused; no retry')
            result = self.watch(registered)
            self.rearm(); self.save('postflight-drain.json', S.require_drained()); clear(); H.verify()
            S.require(not S.read_rows(QUEUE / 'queue-A.txt') and not S.read_rows(QUEUE / 'queue-B.txt'), 'new queued work blocks restoration')
            self.log('sixteen-turn client qualification and clean worker drain passed; restoring prior endpoints once')
            with (self.evidence / 'restore.log').open('w') as log:
                cp = subprocess.run(['/usr/bin/python3', '-B', str(HERE / 'restore_guard.py'), '--manifest-sha256', EXPECTED_MANIFEST_SHA, self.suffix], stdin=subprocess.DEVNULL,
                                    stdout=log, stderr=subprocess.STDOUT, cwd=ROOT)
            S.require(cp.returncode == 0, 'restore failed; no retry'); clear()
            self.save('window-result.json', dict(passed=True, at=S.now(), worker=result, restore_suffix=self.suffix,
                lifecycle_only=False, serving_qualification=True, submission_eligible=False, speed_claim=False))
        except BaseException as error:
            failure = error
            self.log('HALT: ' + str(error))
            if self.mutated:
                try: self.incident()
                except BaseException as incident_error: self.log('incident status: ' + str(incident_error))
            self.save('window-result.json', dict(passed=False, error=str(error), launched=self.launched, stop_signalled=self.signalled, client_launched=self.client_launched, retry=False))
            raise
        finally:
            latch_error = None
            try:
                self.rearm()
            except (OSError, RuntimeError) as error:
                latch_error = str(error)
                self.log('final pause state requires review: ' + latch_error)
                self.save('final-latch-check.json', dict(passed=False, error=latch_error,
                                                        original_error=str(failure) if failure else None,
                                                        external_bytes_preserved=True))
            try:
                cp = S.command(['journalctl', '--user', '-u', UNIT + '.service', '--no-pager', '-o', 'cat'])
                (self.evidence / 'worker-journal.log').write_text(cp.stdout + cp.stderr)
                S.require(cp.returncode==0,'worker journal capture failed')
            except BaseException as journal_error:
                if failure is None:
                    self.save('window-result.json',dict(passed=False,error='journal capture: '+str(journal_error),retry=False))
                    raise
                failure.add_note('Secondary journal capture failure: '+str(journal_error)[:2048])
            if latch_error is not None and failure is None:
                result = self.evidence / 'window-result.json'
                if result.exists(): (self.evidence / 'window-result-before-latch-refusal.json').write_bytes(result.read_bytes())
                self.save('window-result.json', dict(passed=False, error='final pause refusal: ' + latch_error,
                                                       launched=self.launched, retry=False))
                raise RuntimeError('final pause refusal: ' + latch_error)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true'); mode.add_argument('--run', action='store_true')
    parser.add_argument('--restore-suffix', required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); admission()
    evidence = args.output.absolute()
    S.require(evidence.parent == (HERE / 'evidence').resolve(), 'new direct child of controller evidence required')
    if args.check:
        print(json.dumps(dict(passed=True, read_only=True, preflight=check(args.restore_suffix, evidence)))); return
    (HERE / 'evidence').mkdir(exist_ok=True)
    with S.locked(HERE / 'window.lock'): Window(evidence, args.restore_suffix).execute()


if __name__ == '__main__': main()
