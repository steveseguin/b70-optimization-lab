#!/usr/bin/env python3
"""Single manually coordinated packet200 lifecycle window; no retry/resume path."""
import argparse
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
H=load('_p200_driver_helpers',_THIS/'helpers.py')
C=load('_p200_frozen_window_contract',_THIS/'window.py')
S = H.S
HERE, ROOT, QUEUE, UNIT = H.HERE, H.ROOT, S.QUEUE, S.UNIT
PACKET = C.PACKET
A = load('_p200_execution_adapter', PACKET/'run.py')
WORKER = PACKET/'run.py'
STAGE = A.STAGE
OUTPUT = STAGE/'output'
REVIEW = A.REVIEW
PYTHON = A.PYTHON
CHECKPOINT_ROOT = STAGE/'checkpoints'
EXPECTED_MANIFEST_SHA = None


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


def status():
    cp = S.command(['systemctl', '--user', 'show', UNIT + '.service',
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
    stage=C.staging_identity(STAGE)
    S.require(controller.get('staging_identity')==stage,'root-admitted private staging identity differs')
    S.require(re.fullmatch(r'20261023-restore[0-9]+', suffix), 'explicit fresh restore suffix required')
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


class Window:
    def __init__(self, evidence, suffix):
        self.evidence, self.suffix = evidence, suffix
        self.pause = {}
        self.mutated = self.launched = self.signalled = False
        self.listener_announced=False

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
                with path.open('xb') as file: file.write(('packet200 incident ' + S.now() + '\n').encode())
            except FileExistsError: pass
        if self.launched and S.active(UNIT) and not self.signalled:
            safe_stop(UNIT); self.signalled = True
            cp = S.command(['systemctl', '--user', 'kill', '--kill-whom=main', '--signal=SIGTERM', UNIT + '.service'])
            self.save('cooperative-stop.json', dict(sent_once=True, rc=cp.returncode, stdout=cp.stdout, stderr=cp.stderr))
            S.require(cp.returncode == 0, 'main-process cooperative stop failed; no escalation')
        end = time.monotonic() + 900
        while self.launched and S.active(UNIT) and time.monotonic() < end: time.sleep(5)
        S.require(not self.launched or not S.active(UNIT), 'worker retained after drain deadline; no kill/restore')

    def watch(self, plan_row):
        end = time.monotonic() + 7500  # native/worker deadline7200 plus graceful completion allowance
        final_rechecks = 0
        while time.monotonic() < end:
            clear()
            S.require(not (QUEUE / 'PAUSE-A').exists() and (QUEUE / 'PAUSE-B').read_bytes() == self.pause['B'], 'pause changed while worker active')
            events=OUTPUT/'control/events.jsonl'
            if not self.listener_announced and events.exists():
                # Read-only announcement; client orchestration is separate and never generates here.
                with events.open() as event_file: event_text=event_file.read(1024*1024)
                for line in event_text.splitlines():
                    try: event=json.loads(line)
                    except json.JSONDecodeError: continue
                    if event.get('event')=='listener':
                        self.log('listener '+json.dumps(event,sort_keys=True));self.listener_announced=True;break
            state = status()  # exactly one unit observation per poll, tolerating normal process exit
            if state.get('ActiveState') not in S.ACTIVE:
                S.require(state.get('ActiveState') == 'inactive' and state.get('Result') == 'success'
                          and state.get('ExecMainStatus') == '0', 'worker unit did not succeed')
                try:
                    # Physical drain is independent of worker JSON and required before acceptance.
                    drain=S.require_drained()
                    self.save('terminal-passive-drain.json',drain)
                    result = terminal(plan_row,state,passive_drained=True)
                except (FileNotFoundError, json.JSONDecodeError):
                    final_rechecks += 1
                    S.require(final_rechecks <= 2, 'final worker receipt unavailable after exit')
                else: return result
            time.sleep(5)
        raise RuntimeError('worker watch deadline; no retry')

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
            self.log('bounded lifecycle and clean worker drain passed; restoring prior endpoints once')
            with (self.evidence / 'restore.log').open('w') as log:
                cp = subprocess.run(['/usr/bin/python3', '-B', str(HERE / 'restore_guard.py'), '--manifest-sha256', EXPECTED_MANIFEST_SHA, self.suffix], stdin=subprocess.DEVNULL,
                                    stdout=log, stderr=subprocess.STDOUT, cwd=ROOT)
            S.require(cp.returncode == 0, 'restore failed; no retry'); clear()
            self.save('window-result.json', dict(passed=True, at=S.now(), worker=result, restore_suffix=self.suffix,
                lifecycle_only=result['validation']['lifecycle_only'], serving_qualification=False))
        except BaseException as error:
            failure = error
            self.log('HALT: ' + str(error))
            if self.mutated:
                try: self.incident()
                except BaseException as incident_error: self.log('incident status: ' + str(incident_error))
            self.save('window-result.json', dict(passed=False, error=str(error), launched=self.launched, stop_signalled=self.signalled, retry=False))
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
