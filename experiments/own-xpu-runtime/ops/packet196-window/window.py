#!/usr/bin/env python3
"""Manual, single-attempt packet196 qualification window; --check is read-only."""
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
import safety as S

HERE, ROOT, QUEUE, PACKET, UNIT = S.HERE, S.ROOT, S.QUEUE, S.PACKET, S.UNIT
ORCH = HERE.parent / 'packet196-orchestration'
LAUNCHER = ORCH / 'launch_chain.sh'
CHAIN_OUTPUT = PACKET / 'evidence/card0-diet-a'
FAULT_REVIEW = PACKET / 'evidence/fault-review-diet-a.json'
ORDER = ('K1a', 'K1b', 'KD', 'W2m', 'WS', 'WS128x', 'WS128')
CHAIN_DEADLINE = 7200


def incident_latches():
    return [p for p in (QUEUE / 'STOP-A', QUEUE / 'STOP-B', CHAIN_OUTPUT / 'STOP') if os.path.lexists(p)]


def faults_clear():
    """Also exported to the copied restore/validator: no requests after external STOP."""
    S.faults_clear()
    S.require(not incident_latches(), 'incident STOP latch present; no new launch or endpoint request')


def chain_status():
    cp = S.command(['systemctl', '--user', 'show', UNIT + '.service',
                    '--property=ActiveState,SubState,Result,ExecMainStatus,Restart,SendSIGKILL,TimeoutStopUSec,MainPID'])
    S.require(cp.returncode == 0, 'cannot read chain unit status')
    return dict(line.split('=', 1) for line in cp.stdout.splitlines() if '=' in line)


def ensure_chain_stop_properties():
    p = chain_status()
    S.require(p.get('Restart') == 'no' and p.get('SendSIGKILL') == 'no' and p.get('TimeoutStopUSec') == 'infinity',
              'chain unit stop properties differ from sealed launcher')


def verify_readiness():
    ready = json.loads((PACKET / 'READY-FOR-DEVICE.json').read_text())
    mirror = json.loads((ORCH / 'READY-FOR-DEVICE.json').read_text())
    S.require(ready == mirror and ready.get('ready_for_device_chain') is True and ready.get('passed') is True
              and ready.get('last_packet_write') is True and ready.get('final_checks_sha256'), 'final READY missing or mirror differs')
    S.require(ready.get('chain_unit') == UNIT and ready.get('windows') == list(ORDER), 'wrong registered chain identity')
    raw = json.loads((PACKET / 'ready.json').read_text())['chain_command']
    S.require(ready.get('chain_command') == raw and hashlib.sha256(raw.encode()).hexdigest() == ready['chain_command_digest_sha256'],
              'registered command digest mismatch')
    cp = S.command(S.PY + [ORCH / 'verify_ready.py'], timeout=1800)
    S.require(cp.returncode == 0, 'sealed verify_ready refused: ' + cp.stderr[-800:])
    return dict(ready_sha256=S.sha(PACKET / 'READY-FOR-DEVICE.json'), launcher_sha256=S.sha(LAUNCHER),
                command_sha256=ready['chain_command_digest_sha256'], verifier_stdout=cp.stdout)


def resume_review(path):
    """One explicitly reviewed endpoint-state refusal; never archives/clears a latch."""
    review = json.loads(Path(path).read_text())
    failed = HERE / 'evidence/window-a'
    required = ('window-result.json', 'preflight.json', 'launcher.log', 'post-stop-drain.json',
                'PAUSE-A.before', 'PAUSE-B.before', 'STOP-A.archived')
    S.require(review.get('schema') == 'packet196.predevice-resume-review.v1' and review.get('reviewed') is True
              and review.get('predevice_refusal') == 'systemctl-is-active-rc4-inactive'
              and review.get('chain_launched') is False and review.get('stop_manually_archived') is True,
              'explicit reviewed predevice classification required')
    pins = review.get('prior_files_sha256')
    S.require(isinstance(pins, dict) and set(pins) == set(required), 'complete original refusal provenance required')
    for name in required:
        S.require(S.sha(failed / name) == pins[name], 'prior refusal provenance changed: ' + name)
    result = json.loads((failed / 'window-result.json').read_text())
    S.require(result.get('passed') is False and result.get('completed') == [] and result.get('stop_signalled') is False
              and result.get('launch_attempted') is True and result.get('retry') is False
              and result.get('error') == 'sealed chain launcher failed; no retry', 'original attempt is not an unsignalled predevice refusal')
    log = (failed / 'launcher.log').read_text()
    S.require(re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ p196-launch REFUSED: cannot establish endpoint state for qwen38-27b-fp8\n', log),
              'original launcher log is not the reviewed early endpoint-state refusal')
    S.require(re.fullmatch(r'packet196 window halted [^\n]+\n', (failed / 'STOP-A.archived').read_text()), 'archived STOP has unexpected owner/content')
    previous = json.loads((failed / 'preflight.json').read_text())
    drained = json.loads((failed / 'post-stop-drain.json').read_text())
    inventory = drained.get('privileged_passive_device_inventory', {})
    S.require(inventory.get('passed') is True and inventory.get('device_opens') == 0 and not inventory.get('holders')
              and not inventory.get('errors') and drained.get('coordinator_guards_both_lanes') is True, 'original drain proof failed')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    S.require(previous['boot'] == boot == review.get('boot_id'), 'resume boot differs')
    S.require(previous['binding']['launcher_sha256'] == review.get('previous_launcher_sha256')
              and S.sha(LAUNCHER) == review.get('replacement_launcher_sha256')
              and review['replacement_launcher_sha256'] != review['previous_launcher_sha256'], 'review must bind a repaired launcher')
    ready = json.loads((PACKET / 'READY-FOR-DEVICE.json').read_text())
    S.require(previous['binding']['command_sha256'] == ready['chain_command_digest_sha256'] == review.get('chain_command_sha256'),
              'resume changed registered device command')
    for lane in ('A', 'B'):
        S.require((QUEUE / f'PAUSE-{lane}').read_bytes() == (failed / f'PAUSE-{lane}.before').read_bytes(), 'original pause bytes changed')
    cp = S.command(['systemctl', '--user', 'show', UNIT + '.service', '--property=LoadState,MainPID'])
    state = dict(line.split('=', 1) for line in cp.stdout.splitlines() if '=' in line)
    S.require(cp.returncode == 0 and state.get('LoadState') == 'not-found' and state.get('MainPID') == '0',
              'chain unit exists or ownership is unknown: not a proven unlaunched attempt')
    S.require(not CHAIN_OUTPUT.exists() and not FAULT_REVIEW.exists() and not (failed / 'cooperative-stop.json').exists(),
              'prior device launch or signal evidence exists')
    S.require(not incident_latches(), 'incident latches must be manually reviewed/archived first')
    return dict(review_path=str(Path(path).resolve()), review_sha256=S.sha(path), previous=previous,
                original_window=str(failed), prior_files_sha256=pins, endpoints_already_drained=True)


def check(suffix, output, resume=None):
    S.require(re.fullmatch(r'20261023-restore[0-9]+', suffix), 'explicit fresh restore suffix required')
    S.require(not output.exists(), 'fresh coordinator evidence directory required')
    S.require(not CHAIN_OUTPUT.exists() and not FAULT_REVIEW.exists(), 'prior chain output/fault review exists; no automatic retry')
    inf = Path('/home/steve/inference')
    for name in (suffix, 'qwen38-27b-fp8-card0-' + suffix, 'qwen38-27b-fp8-card3-' + suffix, 'qwen38-27b-vision-' + suffix):
        S.require(not (inf / name).exists(), 'restore destination exists: ' + name)
    S.require(shutil.disk_usage(ROOT).free >= 27_000_000_000, 'root free below 27 GB')
    for lane in ('A', 'B'):
        S.require((QUEUE / f'PAUSE-{lane}').is_file(), 'both lanes must start paused')
        S.require(not S.read_rows(QUEUE / f'queue-{lane}.txt'), 'outstanding queued work')
    faults_clear()
    S.no_owners()
    status = chain_status()
    S.require(status.get('ActiveState') in ('inactive', ''), 'prior chain unit is not inactive; inspect, never reset')
    # Self may be the enclosing window unit; the sealed launcher applies the same exception.
    self_unit = next((l.rsplit('/', 1)[-1] for l in Path('/proc/self/cgroup').read_text().splitlines() if l.startswith('0::')), '')
    cp = S.command(['systemctl', '--user', 'list-units', 'lanequeue-*', 'window-*', 'packet*',
                    '--state=active,activating,deactivating,reloading', '--no-legend', '--plain'])
    busy = [line.split()[0] for line in cp.stdout.splitlines() if line.split() and line.split()[0] != self_unit]
    S.require(cp.returncode == 0 and not busy, 'another experiment unit active or unit discovery failed: ' + str(busy))
    states = {}
    resumption = resume_review(resume) if resume else None
    for unit in S.ENDPOINTS:
        if resumption:
            live = S.properties(unit)
            S.require(live.get('ActiveState') == 'inactive', 'resume endpoint is not inactive: ' + unit)
            states[unit] = resumption['previous']['endpoints'][unit]
        else:
            S.require(S.properties(unit).get('ActiveState') == 'active', 'expected owner endpoint inactive: ' + unit)
            states[unit] = S.require_safe_stop(unit)
    if not resumption:
        S.endpoint_idle()
    for lane in ('A', 'B'):
        backend, _ = S.backend(); backend.guards(lane)
    binding = verify_readiness()
    return dict(at=S.now(), binding=binding, endpoints=states, boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                chain_unit=UNIT, chain_output=str(CHAIN_OUTPUT), windows=list(ORDER), metadata_only=True, resume_predevice=resumption)


def verify_gate(name, boot, build_sha):
    row = json.loads((CHAIN_OUTPUT / name / 'window.json').read_text())
    expected = dict(window='K1' if name.startswith('K1') else name, passed=True, device_executed=True,
                    child_still_running=False, gpu_count=1, card=0, context=4096, boot_id=boot,
                    build_receipt_sha256=build_sha)
    S.require(all(type(row.get(k)) is type(v) and row[k] == v for k, v in expected.items()), 'incomplete/wrong gate receipt: ' + name)
    return dict(window=name, receipt_sha256=S.sha(CHAIN_OUTPUT / name / 'window.json'))


class Window:
    def __init__(self, output, suffix, resume=None):
        self.output, self.suffix = output, suffix
        self.pause_a = self.pause_b = None
        self.started_mutation = False
        self.launch_attempted = False
        self.stop_signalled = False
        self.gates = []
        self.resume = resume

    def log(self, message):
        line = S.now() + ' ' + message
        print(line, flush=True)
        with (self.output / 'driver.log').open('a') as file:
            file.write(line + '\n')

    def save(self, name, data):
        (self.output / name).write_text(json.dumps(data, indent=2) + '\n')

    def rearm(self):
        if not (QUEUE / 'PAUSE-A').exists():
            with (QUEUE / 'PAUSE-A').open('xb') as file:
                file.write(self.pause_a)
        S.require((QUEUE / 'PAUSE-A').read_bytes() == self.pause_a, 'PAUSE-A changed externally; retained')
        S.require((QUEUE / 'PAUSE-B').read_bytes() == self.pause_b, 'PAUSE-B changed externally; retained')

    def stop_incident(self):
        """Boundary stop first; a live active fault/failure gets one coordinator-only TERM."""
        self.rearm()
        for path in (QUEUE / 'STOP-A', CHAIN_OUTPUT / 'STOP'):
            if not path.parent.exists():
                continue
            try:
                with path.open('xb') as file:
                    file.write(('packet196 window halted ' + S.now() + '\n').encode())
            except FileExistsError:
                pass  # External incident information is never overwritten or removed.
        if self.launch_attempted and S.active(UNIT) and not self.stop_signalled:
            ensure_chain_stop_properties()
            self.stop_signalled = True
            cp = S.command(['systemctl', '--user', 'kill', '--kill-whom=main', '--signal=SIGTERM', UNIT + '.service'])
            self.save('cooperative-stop.json', dict(at=S.now(), sent_once=True, target='chain coordinator MainPID only',
                                                   rc=cp.returncode, stdout=cp.stdout, stderr=cp.stderr))
            S.require(cp.returncode == 0, 'cooperative main-process stop request failed; no escalation')
        deadline = time.monotonic() + 900
        while self.launch_attempted and S.active(UNIT) and time.monotonic() < deadline:
            time.sleep(5)
        S.require(not self.launch_attempted or not S.active(UNIT), 'chain still active after drain bound; latches retained, no kill/restore')

    def watch(self, boot, build_sha):
        deadline = time.monotonic() + CHAIN_DEADLINE
        completed = []
        unreadable = 0
        exit_rechecks = 0
        while time.monotonic() < deadline:
            faults_clear()
            S.require(not (QUEUE / 'PAUSE-A').exists(), 'external PAUSE-A: stop at chain boundary')
            S.require((QUEUE / 'PAUSE-B').read_bytes() == self.pause_b, 'PAUSE-B changed')
            path = CHAIN_OUTPUT / 'queue.json'
            row = None
            if path.exists():
                try:
                    row = json.loads(path.read_text())
                    unreadable = 0
                except (json.JSONDecodeError, FileNotFoundError):
                    unreadable += 1  # persist() writes in place; tolerate only a bounded metadata race.
                    S.require(unreadable <= 6, 'chain queue receipt unreadable for 30 seconds')
            if row is not None:
                S.require(not row.get('error') and row.get('child_still_running') is not True, 'chain failure: ' + str(row.get('error')))
                done = row.get('completed')
                S.require(isinstance(done, list) and done == list(ORDER[:len(done)]) and done[:len(completed)] == completed,
                          'chain completed windows are not a monotonic registered prefix')
                for name in done[len(completed):]:
                    receipt = verify_gate(name, boot, build_sha)
                    self.gates.append(receipt)
                    self.log('GATE ' + name + ' passed')
                completed = done
                self.save('gate-progress.json', dict(completed=completed, gates=self.gates, running=row.get('running')))
                if row.get('passed') is True:
                    S.require(completed == list(ORDER) and row.get('running') is None and isinstance(row.get('finished_utc_ns'), int),
                              'chain passed flag without complete seven-window receipts')
            # One unit sample per iteration. It may exit after we read an earlier
            # in-place queue snapshot; allow bounded metadata rereads, never a launch retry.
            status = chain_status()
            if status.get('ActiveState') not in S.ACTIVE:
                S.require(status.get('ActiveState') == 'inactive' and status.get('Result') == 'success'
                          and status.get('ExecMainStatus') == '0', 'chain unit failed or exit status unavailable')
                if row is not None and row.get('passed') is True:
                    return dict(queue_sha256=S.sha(path), windows=self.gates, status=status)
                exit_rechecks += 1
                S.require(exit_rechecks <= 2, 'chain unit exited without complete successful receipt')
            time.sleep(5)
        raise RuntimeError('chain watch deadline; no retry')

    def execute(self):
        preflight = check(self.suffix, self.output, self.resume)
        self.output.mkdir()
        self.pause_a = (QUEUE / 'PAUSE-A').read_bytes()
        self.pause_b = (QUEUE / 'PAUSE-B').read_bytes()
        self.save('preflight.json', preflight)
        for lane, value in (('A', self.pause_a), ('B', self.pause_b)):
            (self.output / f'PAUSE-{lane}.before').write_bytes(value)
        success = False
        try:
            faults_clear()
            self.started_mutation = True
            if self.resume:
                S.require(preflight.get('resume_predevice', {}).get('endpoints_already_drained') is True, 'resume admission proof absent')
                self.log('continuing manually reviewed predevice refusal; endpoints already drained, no stop/restart requested')
            else:
                S.endpoint_idle()
                self.log('stopping the three idle owner endpoints gracefully once')
                for unit in S.ENDPOINTS:
                    faults_clear()
                    S.require_safe_stop(unit)
                    cp = S.command(['systemctl', '--user', 'stop', '--no-block', unit + '.service'])
                    S.require(cp.returncode == 0, 'endpoint stop request failed: ' + unit)
            deadline = time.monotonic() + 600
            while any(S.active(unit) for unit in S.ENDPOINTS) and time.monotonic() < deadline:
                faults_clear(); time.sleep(5)
            S.require(not any(S.active(unit) for unit in S.ENDPOINTS), 'endpoints did not drain; no escalation')
            self.save('post-stop-drain.json', S.require_drained())
            faults_clear()
            S.require(S.sha(LAUNCHER) == preflight['binding']['launcher_sha256'], 'sealed launcher changed during admission')
            S.require((QUEUE / 'PAUSE-A').read_bytes() == self.pause_a and (QUEUE / 'PAUSE-B').read_bytes() == self.pause_b, 'pause changed before launch')
            with S.locked(QUEUE / 'edit-A.lock'):
                S.require(not S.read_rows(QUEUE / 'queue-A.txt'), 'lane A queue changed before launch')
                S.require((QUEUE / 'PAUSE-A').read_bytes() == self.pause_a, 'PAUSE-A changed while acquiring edit lock')
                (QUEUE / 'PAUSE-A').unlink()
            faults_clear()
            self.launch_attempted = True
            self.log('invoking exact sealed packet196 launcher once')
            cp = S.command(['/usr/bin/bash', LAUNCHER], timeout=3600)
            (self.output / 'launcher.log').write_text(cp.stdout + cp.stderr)
            S.require(cp.returncode == 0, 'sealed chain launcher failed; no retry')
            ensure_chain_stop_properties()
            done = self.watch(preflight['boot'], S.sha(PACKET / 'build-receipt.json'))
            self.rearm()
            self.save('postflight-drain.json', S.require_drained())
            faults_clear()
            S.require(not S.read_rows(QUEUE / 'queue-A.txt') and not S.read_rows(QUEUE / 'queue-B.txt'), 'new queued work blocks restoration')
            self.log('all seven gates passed and host drained; restoring prior owner endpoints once')
            with (self.output / 'restore.log').open('w') as log:
                cp = subprocess.run(['/usr/bin/python3', '-B', str(HERE / 'restore.py'), self.suffix], cwd=ROOT,
                                    stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
            S.require(cp.returncode == 0, 'restore failed; no retry')
            faults_clear()
            success = True
            self.save('window-result.json', dict(passed=True, at=S.now(), chain=done, restore_suffix=self.suffix))
        except BaseException as error:
            self.log('HALT: ' + str(error))
            if self.started_mutation:
                try:
                    self.stop_incident()
                except BaseException as stop_error:
                    self.log('incident drain status: ' + str(stop_error))
            self.save('window-result.json', dict(passed=False, at=S.now(), error=str(error), completed=self.gates,
                                                  launch_attempted=self.launch_attempted, retry=False, stop_signalled=self.stop_signalled))
            raise
        finally:
            self.rearm()
            cp = S.command(['journalctl', '--user', '-u', UNIT + '.service', '--no-pager', '-o', 'cat'])
            (self.output / 'chain-journal.log').write_text(cp.stdout + cp.stderr)
            self.log('window closed' if success else 'window halted; no retry or automatic recovery')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true'); mode.add_argument('--run', action='store_true')
    parser.add_argument('--restore-suffix', required=True); parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--resume-predevice', type=Path, help='explicit reviewed window-a endpoint-state refusal; STOP must already be manually archived')
    args = parser.parse_args()
    output = args.output.resolve()
    S.require(output.parent == (HERE / 'evidence').resolve(), 'fresh direct child of coordinator evidence required')
    if args.check:
        print(json.dumps(dict(passed=True, read_only=True, preflight=check(args.restore_suffix, output, args.resume_predevice))))
        return
    (HERE / 'evidence').mkdir(exist_ok=True)
    with S.locked(HERE / 'window.lock'):
        Window(output, args.restore_suffix, args.resume_predevice).execute()


if __name__ == '__main__':
    main()
