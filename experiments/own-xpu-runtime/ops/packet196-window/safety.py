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
PACKET = ROOT / 'experiments/own-xpu-runtime/stage2/packet196-onecard-diet-chain'
COORD = Path('/home/steve/own-xpu-runtime-results/coordination/chain-lanes-v1')
PROPOSAL = QUEUE / 'proposed-p58-dietengine-one-card-A.txt'
JOB = 'packet58dietengine-one-card-v5-A'
UNIT = 'packet58-onecard-diet-a'
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


@contextmanager
def locked(path):
    with path.open('a+') as file:
        fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
