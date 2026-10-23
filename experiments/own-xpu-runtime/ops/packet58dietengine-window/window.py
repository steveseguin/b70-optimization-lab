#!/usr/bin/env python3
"""One manual, fail-closed packet58 diet engine screen. --check is read-only."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.request

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
QUEUE = HERE.parent / 'lane-queue'
PACKET = ROOT / 'experiments/own-xpu-runtime/stage2/packet58-onecard-diet-engine'
COORD = Path('/home/steve/own-xpu-runtime-results/coordination/chain-lanes-v1')
PROPOSAL = QUEUE / 'proposed-p58-dietengine-one-card-A.txt'
JOB = 'packet58dietengine-one-card-v5-A'
UNIT = 'lanequeue-A35'
ENDPOINTS = ('qwen38-27b-vision', 'qwen38-27b-fp8-tp1-test', 'qwen38-27b-fp8')
SAFE_PROPS = ['--property=Restart=no', '--property=SendSIGKILL=no',
              '--property=TimeoutStopSec=infinity', '--property=KillMode=process', '--property=ExitType=cgroup']
PY = ['/usr/bin/nice', '-n', '19', '/usr/bin/taskset', '-c', '8-15,24-31', '/usr/bin/python3', '-B']
ACTIVE = ('active', 'activating', 'deactivating', 'reloading')
BENIGN_ROW_EVENTS = ('START', 'WAIT-HOST-ADMISSION', 'WAIT-OTHER-LANE-LIVE', 'WAIT-DRAIN-SPACING')
TERMINAL_EVENTS = ('FAILED', 'FAILED-status', 'FAILED-postflight', 'REFUSED-fast', 'REFUSED-PREDEVICE',
                   'REPORT-FAILED', 'STOP', 'SKIPPED-DEPENDENCY', 'SKIPPED', 'ALERT')


def now():
    return datetime.now(timezone.utc).isoformat()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(argv, timeout=60):
    return subprocess.run(list(map(str, argv)), stdin=subprocess.DEVNULL, capture_output=True,
                          text=True, timeout=timeout, cwd=ROOT)


def properties(unit):
    cp = command(['systemctl', '--user', 'show', unit + '.service', '--property=ActiveState,SubState,Restart,SendSIGKILL,TimeoutStopUSec,KillMode,ControlGroup'])
    require(cp.returncode == 0, 'cannot inspect unit ' + unit)
    return dict(line.split('=', 1) for line in cp.stdout.splitlines() if '=' in line)


def active(unit):
    return properties(unit).get('ActiveState') in ACTIVE


def require_safe_stop(unit):
    p = properties(unit)
    require(p.get('Restart') == 'no' and p.get('SendSIGKILL') == 'no'
            and p.get('TimeoutStopUSec') == 'infinity' and p.get('KillMode') in ('process', 'control-group'),
            'unsafe stop properties: ' + unit)
    return p


def backend():
    sys.path.insert(0, str(QUEUE))
    import lanequeue
    return lanequeue.Backend(), lanequeue.BASE


def faults_clear():
    b, baseline = backend()
    require(b.faults() == baseline, 'new or unreadable kernel fault evidence; halt all new requests')


def no_owners():
    for lane in ('A', 'B'):
        require(not os.path.lexists(COORD / f'active-lane-{lane}.json'), 'lane ownership marker remains')
        require(not os.path.lexists(QUEUE / f'inflight-{lane}.json'), 'queue inflight record remains')


def device_holders():
    """Root metadata scan so another user's unreadable descriptors cannot count as empty."""
    helper = HERE / 'passive_device_holders.py'
    with Path('/home/steve/SUDOPASSWORD.txt').open('rb') as credential:
        cp = subprocess.run(['/usr/bin/sudo', '-S', '-p', '', '--', '/usr/bin/python3', '-B', str(helper)],
                            stdin=credential, capture_output=True, text=True, timeout=30, cwd=ROOT)
    require(cp.returncode in (0, 1) and not cp.stderr.strip(), 'privileged passive device ownership scan failed')
    try:
        row = json.loads(cp.stdout)
    except ValueError:
        raise RuntimeError('invalid passive ownership scan receipt') from None
    require(row.get('metadata_only') is True and row.get('device_opens') == 0,
            'ownership scan did not attest metadata-only operation')
    require(cp.returncode == 0 and row.get('passed') is True and not row.get('holders') and not row.get('errors'),
            'device holders or unreadable ownership remain: ' + json.dumps(row))
    return row


def require_drained():
    require(not active(UNIT), 'queue driver still active: retain STOP and PAUSE, do not restore')
    no_owners()
    inventory = device_holders()
    b, _ = backend()
    b.guards('A')
    b.guards('B')
    return dict(privileged_passive_device_inventory=inventory, coordinator_guards_both_lanes=True)


def endpoint_idle():
    """Metadata only: never submit generation while checking admission."""
    for port in (18130, 18131):
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/metrics', timeout=10) as response:
            text = response.read().decode()
        for metric in ('num_requests_running', 'num_requests_waiting'):
            values = [float(m.group(1)) for line in text.splitlines()
                      if (m := re.match(r'^vllm:' + metric + r'(?:\{[^}]*\})?\s+([0-9.eE+-]+)', line))]
            require(values and all(v == 0 for v in values), f'endpoint {port} busy or {metric} unavailable')
    with urllib.request.urlopen('http://127.0.0.1:18100/slots', timeout=10) as response:
        slots = json.load(response)
    require(isinstance(slots, list) and slots and all(s.get('is_processing') is False for s in slots),
            'vision slots busy or idle status unavailable')


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip() and not line.lstrip().startswith('#')]


def check(suffix, output):
    require(re.fullmatch(r'20261023-restore[0-9]+', suffix), 'explicit fresh restore suffix required')
    require(not output.exists(), 'fresh window output required')
    require(not (Path('/home/steve/inference') / suffix).exists(), 'restore destination already exists')
    for base in ('qwen38-27b-fp8-card0-', 'qwen38-27b-fp8-card3-', 'qwen38-27b-vision-'):
        require(not (Path('/home/steve/inference') / (base + suffix)).exists(), 'restore state directory already exists')
    require(shutil.disk_usage(ROOT).free >= 27_000_000_000, 'root free below 27 GB')
    rows = read_rows(PROPOSAL)
    require(len(rows) == 1 and rows[0]['name'] == JOB and rows[0]['lane'] == 'A', 'wrong proposal')
    ready = json.loads((PACKET / 'READY-FOR-DEVICE.json').read_text())
    require(ready.get('ready_for_device') is True and ready.get('proposal_sha256') == sha(PROPOSAL), 'READY/proposal mismatch')
    for lane in ('A', 'B'):
        require((QUEUE / f'PAUSE-{lane}').is_file(), 'both lanes must be paused')
        require(not (QUEUE / f'STOP-{lane}').exists(), 'existing STOP latch requires review')
        require(not read_rows(QUEUE / f'queue-{lane}.txt'), 'outstanding queued work: do not overwrite')
    cp = command(['systemctl', '--user', 'list-units', 'lanequeue-*', 'packet*',
                  '--state=active,activating,deactivating,reloading', '--no-legend', '--plain'])
    require(cp.returncode == 0 and not cp.stdout.strip(), 'another experiment/queue unit is active or unit discovery failed')
    require(not active(UNIT), 'window runner already active')
    no_owners()
    for unit in ENDPOINTS:
        require(properties(unit).get('ActiveState') == 'active', 'expected restored endpoint not active: ' + unit)
        require_safe_stop(unit)
    endpoint_idle()
    faults_clear()
    for lane in ('A', 'B'):
        b, _ = backend()
        b.guards(lane)
    return rows[0]


@contextmanager
def locked(path):
    with path.open('a+') as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


class Window:
    def __init__(self, output, suffix):
        self.output, self.suffix = output, suffix
        self.pause_a = self.pause_b = None
        self.offset = 0
        self.pending = ''
        self.mutated = False
        self.stop_owned = False
        self.stop_bytes = None
        self.stop_identity = None
        self.events = []

    def save(self, name, data):
        (self.output / name).write_text(json.dumps(data, indent=2) + '\n')

    def log(self, message):
        line = now() + ' ' + message
        print(line, flush=True)
        with (self.output / 'driver.log').open('a') as f:
            f.write(line + '\n')

    def rearm(self):
        require((QUEUE / 'PAUSE-B').read_bytes() == self.pause_b, 'PAUSE-B changed: coordinator review required')
        if not (QUEUE / 'PAUSE-A').exists():
            (QUEUE / 'PAUSE-A').write_bytes(self.pause_a)
        require((QUEUE / 'PAUSE-A').read_bytes() == self.pause_a, 'PAUSE-A changed externally; retained')

    def stop_boundary(self):
        self.rearm()
        stop = QUEUE / 'STOP-A'
        if not stop.exists():
            self.stop_bytes = ('packet58dietengine window stop ' + now() + '\n').encode()
            with stop.open('xb') as file:
                file.write(self.stop_bytes)
            info = stop.stat()
            self.stop_identity = (info.st_dev, info.st_ino)
            self.stop_owned = True
        deadline = time.monotonic() + 900
        while active(UNIT) and time.monotonic() < deadline:
            time.sleep(5)
        require(not active(UNIT), 'runner did not drain in 900 s; STOP-A retained; no kill or restore')

    def archive_owned_stop(self):
        stop = QUEUE / 'STOP-A'
        require(self.stop_owned and self.stop_bytes is not None, 'foreign STOP-A blocks restore; retained for review')
        info = stop.stat()
        require((info.st_dev, info.st_ino) == self.stop_identity and stop.read_bytes() == self.stop_bytes,
                'STOP-A changed externally; retained, restore refused')
        (self.output / 'STOP-A.archived').write_bytes(self.stop_bytes)
        # Other cooperating queue writers use edit-A.lock. Refuse any observed replacement.
        stop.unlink()

    def next_events(self):
        path = QUEUE / 'events-A.jsonl'
        require(path.stat().st_size >= self.offset, 'events file truncated')
        with path.open() as f:
            f.seek(self.offset)
            data = f.read()
            self.offset = f.tell()
        lines = (self.pending + data).split('\n')
        self.pending = lines.pop()
        return [json.loads(line) for line in lines if line]

    def watch(self):
        deadline = time.monotonic() + 5400
        while time.monotonic() < deadline:
            faults_clear()
            for row in self.next_events():
                self.events.append(row)
                self.log('EVENT ' + json.dumps(row))
                require(row.get('event') not in TERMINAL_EVENTS, 'lane stopped or failed: ' + json.dumps(row))
                if row.get('name') != JOB:
                    require(row.get('event') not in ('START', 'ALERT'), 'unexpected lane activity')
                    continue
                if row.get('event') == 'DONE':
                    return row
                require(row.get('event') in BENIGN_ROW_EVENTS,
                        'row did not succeed: ' + json.dumps(row))
            require(active(UNIT), 'runner exited without DONE')
            time.sleep(5)
        raise RuntimeError('window watch deadline; no retry')

    def execute(self):
        job = check(self.suffix, self.output)
        self.output.mkdir()
        self.pause_a = (QUEUE / 'PAUSE-A').read_bytes()
        self.pause_b = (QUEUE / 'PAUSE-B').read_bytes()
        self.save('preflight.json', dict(at=now(), proposal_sha256=sha(PROPOSAL), job=job, boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()))
        (self.output / 'PAUSE-A.before').write_bytes(self.pause_a)
        (self.output / 'PAUSE-B.before').write_bytes(self.pause_b)
        success = False
        try:
            with locked(QUEUE / 'edit-A.lock'):
                require(not read_rows(QUEUE / 'queue-A.txt'), 'queue changed during preflight')
                (self.output / 'queue-A.before').write_bytes((QUEUE / 'queue-A.txt').read_bytes())
                (QUEUE / 'queue-A.txt').write_text(json.dumps(job) + '\n')
                self.mutated = True
            cp = command(PY + [QUEUE / 'lanequeue.py', 'plan', '--lane', 'A'], timeout=900)
            (self.output / 'live-plan.log').write_text(cp.stdout + cp.stderr)
            result = [json.loads(line) for line in cp.stdout.splitlines() if line.startswith('{')]
            require(cp.returncode == 0 and len(result) == 1 and result[0].get('plan') == 'passed', 'live plan refused')
            self.log('live plan passed; gracefully stopping idle endpoints once')
            endpoint_idle()
            faults_clear()
            for unit in ENDPOINTS:
                require_safe_stop(unit)
                cp = command(['systemctl', '--user', 'stop', '--no-block', unit + '.service'])
                require(cp.returncode == 0, 'stop request failed: ' + unit)
            deadline = time.monotonic() + 600
            while any(active(u) for u in ENDPOINTS) and time.monotonic() < deadline:
                faults_clear()
                time.sleep(5)
            require(not any(active(u) for u in ENDPOINTS), 'endpoints did not stop; no escalation')
            self.save('post-stop-drain.json', require_drained())
            mem = next(int(l.split()[1]) * 1024 for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:'))
            require(mem >= 100487123456 + 1024**3, 'host memory admission refused')
            faults_clear()
            event_path = QUEUE / 'events-A.jsonl'
            self.offset = event_path.stat().st_size if event_path.exists() else 0
            # Cursor captured before launch, so fast START/refusal/DONE events cannot disappear.
            require((QUEUE / 'PAUSE-A').read_bytes() == self.pause_a and (QUEUE / 'PAUSE-B').read_bytes() == self.pause_b, 'pause changed')
            (QUEUE / 'PAUSE-A').unlink()
            cp = command(['systemd-run', '--user', '--unit=' + UNIT, '--working-directory=' + str(ROOT), *SAFE_PROPS,
                          '/usr/bin/python3', '-B', QUEUE / 'lanequeue.py', 'run', '--lane', 'A'])
            self.save('runner-launch.json', dict(argv='lanequeue.py run --lane A', rc=cp.returncode, stdout=cp.stdout, stderr=cp.stderr))
            require(cp.returncode == 0, 'runner launch failed; no retry')
            done = self.watch()
            self.stop_boundary()
            self.save('postflight-drain.json', require_drained())
            faults_clear()
            require(not read_rows(QUEUE / 'queue-A.txt'), 'queue not empty after DONE')
            with locked(QUEUE / 'edit-A.lock'):
                self.archive_owned_stop()
            self.log('DONE and clean drain; restoring the three previously active endpoints once')
            with (self.output / 'restore.log').open('w') as log:
                cp = subprocess.run(['/usr/bin/python3', '-B', str(HERE / 'restore.py'), self.suffix], cwd=ROOT,
                                    stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
            require(cp.returncode == 0, 'endpoint restore failed; no retry')
            faults_clear()
            success = True
            self.save('window-result.json', dict(passed=True, at=now(), done=done, restore_suffix=self.suffix))
        except BaseException as error:
            self.log('HALT: ' + str(error))
            if self.mutated:
                try:
                    self.stop_boundary()
                except BaseException as drain_error:
                    self.log('Drain/latch status: ' + str(drain_error))
            self.save('window-result.json', dict(passed=False, at=now(), error=str(error), restore_retry=False, events=self.events))
            raise
        finally:
            self.rearm()
            cp = command(['journalctl', '--user', '-u', UNIT + '.service', '--no-pager', '-o', 'cat'])
            (self.output / 'runner-journal.log').write_text(cp.stdout + cp.stderr)
            self.log('window closed' if success else 'window halted; receipts and latches retained')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--run', action='store_true')
    parser.add_argument('--restore-suffix', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    require(output.parent == (HERE / 'evidence').resolve(), 'output must be a fresh direct child of this driver evidence directory')
    if args.check:
        job = check(args.restore_suffix, output)
        print(json.dumps(dict(passed=True, read_only=True, job=job['name'], output=str(output))))
        return
    (HERE / 'evidence').mkdir(exist_ok=True)
    with locked(HERE / 'window.lock'):
        Window(output, args.restore_suffix).execute()


if __name__ == '__main__':
    main()
