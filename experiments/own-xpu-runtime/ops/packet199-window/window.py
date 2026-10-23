#!/usr/bin/env python3
"""Single manually coordinated packet199 lifecycle window; no retry/resume path."""
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
import helpers as H
S = H.S
HERE, ROOT, QUEUE, UNIT = H.HERE, H.ROOT, S.QUEUE, S.UNIT
PACKET = ROOT / 'experiments/own-xpu-runtime/stage2/packet199-chat-parking'
WORKER = PACKET / 'device_worker.py'
OUTPUT = PACKET / 'evidence/device-p199-chat-A-a'
REVIEW = PACKET / 'evidence/fault-review-device-a.json'
PYTHON = '/home/steve/.venvs/vllm-xpu/bin/python'
CHECKPOINT_ROOT = PACKET / 'evidence/runcheckpoints'
CORRECTNESS = ('A_parent_exact', 'B_parent_exact', 'append_restore_selected', 'append_fresh_tokens_exact',
               'append_fresh_state_exact', 'edited_prefill', 'final_B_repeat', 'postreply_controls_exact',
               'final_release_before_stopped', 'http_usage_exact', 'parking_budget_respected')
IDS = ['a-park', 'b-park', 'a-chat-append', 'a-chat-fresh', 'a-edited', 'final-b-no-park']
CONTROLS = ['parking-' + str(i) for i in range(1, 7)]


def clear():
    S.faults_clear()
    S.require(not any(os.path.lexists(p) for p in (QUEUE / 'STOP-A', QUEUE / 'STOP-B', OUTPUT / 'STOP')),
              'incident latch present; no launch or restore')


# The guarded adapter runs the unchanged p196 restoration/validation sources,
# whose imports bind this module's per-operation guard in the p199 process.
faults_clear = clear


def status():
    cp = S.command(['systemctl', '--user', 'show', UNIT + '.service',
                    '--property=LoadState,ActiveState,Result,ExecMainStatus,MainPID,Restart,SendSIGKILL,TimeoutStopUSec,KillMode'])
    S.require(cp.returncode == 0, 'worker unit status unreadable')
    return dict(line.split('=', 1) for line in cp.stdout.splitlines() if '=' in line)


def plan():
    cp = S.command(S.PY[:6] + [PYTHON, '-B', WORKER, '--plan'], timeout=1800)
    S.require(cp.returncode == 0, 'worker CPU plan refused: ' + cp.stderr[-600:])
    row = json.loads(cp.stdout)
    S.require(row.get('passed') is True and row.get('device_executed') is False, 'worker plan is not a CPU admission proof')
    S.require(row.get('unit') == UNIT and row.get('output') == str(OUTPUT) and row.get('fault_review') == str(REVIEW)
              and row.get('terminal_receipt') == str(OUTPUT / 'worker.json')
              and row.get('checkpoint_root') == str(CHECKPOINT_ROOT), 'worker plan changed fixed lifecycle paths')
    argv = [PYTHON, '-B', str(WORKER), '--authorized-device-window', '--output', str(OUTPUT), '--fault-review', str(REVIEW)]
    S.require(row.get('worker_argv') == argv, 'worker argv differs from fixed invocation')
    ids = row.get('expected_request_ids')
    S.require(ids == IDS, 'exact six request identities required')
    for key in ('host_required_available_bytes', 'planned_write_bytes', 'disk_floor_bytes'):
        S.require(type(row.get(key)) is int and row[key] > 0, 'missing admission value: ' + key)
    S.require(row['disk_floor_bytes'] == 27_000_000_000 and row['planned_write_bytes'] == 671088640
              and row['host_required_available_bytes'] == 98990252032,
              'registered storage or host-memory admission changed')
    S.require(row.get('cpu_affinity') in ('0-3,16-19', '8-15,24-31') and row.get('nice') in (0, 19), 'worker placement not registered')
    review = row.get('fault_review_command')
    S.require(isinstance(review, list) and len(review) >= 5 and review[:2] == [PYTHON, '-B']
              and str(review[2]).startswith(str(PACKET) + '/') and review[-2:] == ['--output', str(REVIEW)], 'fault review command not packet-private/fixed')
    S.require(row.get('protocol') == 'ownrt.request-front.v2' and row.get('expected_controls') == CONTROLS,
              'fixed postreply protocol/control order required')
    S.require(all(type(row.get(k)) is int and row[k] == v for k,v in
                  dict(save_count=5, release_count=1, maximum_output_tokens=896).items()), 'postreply operation/token budget changed')
    return row


def check(suffix, evidence):
    H.verify()
    S.require(re.fullmatch(r'20261023-restore[0-9]+', suffix), 'explicit fresh restore suffix required')
    S.require(not any(os.path.lexists(p) for p in (evidence, OUTPUT, REVIEW, CHECKPOINT_ROOT)),
              'fresh coordinator/worker/review/checkpoint paths required; never retry')
    for name in (suffix, 'qwen38-27b-fp8-card0-' + suffix, 'qwen38-27b-fp8-card3-' + suffix, 'qwen38-27b-vision-' + suffix):
        S.require(not (Path('/home/steve/inference') / name).exists(), 'restore destination already exists')
    S.require(shutil.disk_usage(ROOT).free >= 27_000_000_000, 'root free below 27 GB')
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
        endpoints[unit] = S.require_safe_stop(unit)
        S.require(endpoints[unit].get('ActiveState') == 'active', 'prior endpoint not active: ' + unit)
    S.endpoint_idle()
    registered = plan()
    S.require(shutil.disk_usage(ROOT).free >= registered['disk_floor_bytes'] + registered['planned_write_bytes'],
              'storage floor after planned writes refused before endpoint stop')
    return dict(at=S.now(), endpoints=endpoints, plan=registered, worker_sha256=S.sha(WORKER),
                boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip())


def terminal(plan_row):
    row = json.loads((OUTPUT / 'worker.json').read_text())
    expected = dict(passed=True, device_executed=True, native_process_count=1, model_loads=1,
                    child_still_running=False, safe_to_exit=True, devices_drained=True,
                    save_count=5, release_count=1)
    S.require(all(type(row.get(k)) is type(v) and row[k] == v for k, v in expected.items()), 'worker terminal safety/count proof failed')
    count = row.get('total_output_tokens')
    S.require(type(count) is int and 6 <= count <= 896, 'actual output token count outside registered cap')
    S.require(row.get('completed_requests') == IDS == plan_row['expected_request_ids'], 'incomplete/wrong six-request order')
    S.require(all(row.get('correctness', {}).get(key) is True for key in CORRECTNESS), 'chat lifecycle exactness failed')
    S.require(row.get('completed_controls') == CONTROLS, 'incomplete/wrong six-control order')
    stopped = row.get('stopped', {})
    expected_stop = dict(event='stopped', safe_to_exit=True, reason='request-limit', completed_requests=6,
                         completed_controls=6, discarded_pending=False, pending_request_id='')
    S.require(all(type(stopped.get(k)) is type(v) and stopped[k] == v for k,v in expected_stop.items()),
              'final release/clean stopped proof failed')
    controls = row.get('controls', [])
    S.require(len(controls) == 6 and [c.get('operation_id') for c in controls] == CONTROLS and
              [c.get('event') for c in controls] == ['checkpoint-saved'] * 5 + ['request-released'] and
              all(c.get('final_request') is (i == 5) for i,c in enumerate(controls)),
              'postreply control receipts/final release proof failed')
    return row


class Window:
    def __init__(self, evidence, suffix):
        self.evidence, self.suffix = evidence, suffix
        self.pause = {}
        self.mutated = self.launched = self.signalled = False

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
                with path.open('xb') as file: file.write(('packet199 incident ' + S.now() + '\n').encode())
            except FileExistsError: pass
        if self.launched and S.active(UNIT) and not self.signalled:
            S.require_safe_stop(UNIT); self.signalled = True
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
            state = status()  # exactly one unit observation per poll, tolerating normal process exit
            if state.get('ActiveState') not in S.ACTIVE:
                S.require(state.get('ActiveState') == 'inactive' and state.get('Result') == 'success'
                          and state.get('ExecMainStatus') == '0', 'worker unit did not succeed')
                try: result = terminal(plan_row)
                except (FileNotFoundError, json.JSONDecodeError):
                    final_rechecks += 1
                    S.require(final_rechecks <= 2, 'final worker receipt unavailable after exit')
                else: return result
            time.sleep(5)
        raise RuntimeError('worker watch deadline; no retry')

    def execute(self):
        pre = check(self.suffix, self.evidence)
        self.evidence.mkdir()
        self.pause = {lane:(QUEUE / f'PAUSE-{lane}').read_bytes() for lane in ('A', 'B')}
        self.save('preflight.json', pre)
        for lane, data in self.pause.items(): (self.evidence / f'PAUSE-{lane}.before').write_bytes(data)
        failure = None
        try:
            clear(); S.endpoint_idle(); self.mutated = True
            self.log('stopping the three idle prior endpoints once')
            for unit in S.ENDPOINTS:
                clear(); S.require_safe_stop(unit)
                cp = S.command(['systemctl', '--user', 'stop', '--no-block', unit + '.service'])
                S.require(cp.returncode == 0, 'endpoint stop request failed')
            end = time.monotonic() + 600
            while any(S.active(u) for u in S.ENDPOINTS) and time.monotonic() < end:
                clear(); time.sleep(5)
            S.require(not any(S.active(u) for u in S.ENDPOINTS), 'endpoint drain deadline; no escalation')
            self.save('post-stop-drain.json', S.require_drained())
            registered = pre['plan']; fresh = plan()
            S.require(fresh == registered and S.sha(WORKER) == pre['worker_sha256'], 'worker plan/source changed during admission')
            available = next(int(line.split()[1]) * 1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
            S.require(available >= registered['host_required_available_bytes'] + 1024**3, 'host memory floor refused')
            S.require(shutil.disk_usage(ROOT).free >= registered['disk_floor_bytes'] + registered['planned_write_bytes'], 'storage floor refused')
            clear()
            cp = S.command(S.PY[:6] + registered['fault_review_command'], timeout=1800)
            self.save('fault-review-command.json', dict(rc=cp.returncode, stdout=cp.stdout, stderr=cp.stderr))
            S.require(cp.returncode == 0 and REVIEW.exists(), 'fresh fault review refused')
            clear()
            with S.locked(QUEUE / 'edit-A.lock'):
                S.require(not S.read_rows(QUEUE / 'queue-A.txt') and not S.read_rows(QUEUE / 'queue-B.txt'), 'queue changed during admission')
                S.require(all((QUEUE / f'PAUSE-{lane}').read_bytes() == data for lane,data in self.pause.items()), 'pause changed before launch')
                (QUEUE / 'PAUSE-A').unlink()
            clear(); self.launched = True
            argv = ['systemd-run', '--user', '--unit=' + UNIT, '--working-directory=' + str(ROOT), *S.SAFE_PROPS,
                    '--property=Nice=' + str(registered['nice']), '/usr/bin/taskset', '-c', registered['cpu_affinity'], *registered['worker_argv']]
            cp = S.command(argv)
            self.save('worker-launch.json', dict(argv=argv, rc=cp.returncode, stdout=cp.stdout, stderr=cp.stderr))
            S.require(cp.returncode == 0, 'worker launch refused; no retry')
            result = self.watch(registered)
            self.rearm(); self.save('postflight-drain.json', S.require_drained()); clear(); H.verify()
            S.require(not S.read_rows(QUEUE / 'queue-A.txt') and not S.read_rows(QUEUE / 'queue-B.txt'), 'new queued work blocks restoration')
            self.log('six exact chat requests and clean worker drain passed; restoring prior endpoints once')
            with (self.evidence / 'restore.log').open('w') as log:
                cp = subprocess.run(['/usr/bin/python3', '-B', str(HERE / 'restore_guard.py'), self.suffix], stdin=subprocess.DEVNULL,
                                    stdout=log, stderr=subprocess.STDOUT, cwd=ROOT)
            S.require(cp.returncode == 0, 'restore failed; no retry'); clear()
            self.save('window-result.json', dict(passed=True, at=S.now(), worker=result, restore_suffix=self.suffix))
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
            cp = S.command(['journalctl', '--user', '-u', UNIT + '.service', '--no-pager', '-o', 'cat'])
            (self.evidence / 'worker-journal.log').write_text(cp.stdout + cp.stderr)
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
    args = parser.parse_args(); evidence = args.output.resolve()
    S.require(evidence.parent == (HERE / 'evidence').resolve(), 'new direct child of controller evidence required')
    if args.check:
        print(json.dumps(dict(passed=True, read_only=True, preflight=check(args.restore_suffix, evidence)))); return
    (HERE / 'evidence').mkdir(exist_ok=True)
    with S.locked(HERE / 'window.lock'): Window(evidence, args.restore_suffix).execute()


if __name__ == '__main__': main()
