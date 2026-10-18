"""Compatibility with screen/v3/conditions.py's existing 60-second drain gate.

Hold across an entire chain window: fixture/KD programs exit autonomously, so
Python cannot intercept their last device operation. The future B wrapper can
still admit computation with screen_teardown_admit; its v3 Teardown waits.
Existing sealed engines and screens remain untouched.
"""
import fcntl
import json
import os
from pathlib import Path
import time

from p150_v5_chain_devices import require, process_identity
from p150_v5_lane_admission import atomic_json, DEFAULT_ROOT

DEFAULT_DRAIN_ROOT = Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v3')


class DrainPermit:
    def __init__(self, output, *, root=DEFAULT_DRAIN_ROOT, check=lambda: None,
                 now=time.monotonic, sleep=time.sleep, wait_seconds=1800,
                 reservation=None):
        self.output, self.root, self.check = Path(output), Path(root), check
        self.now, self.sleep, self.wait_seconds = now, sleep, wait_seconds
        self.stream, self.record = None, None
        self.reservation = reservation
        self.boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()

    def __enter__(self):
        require(self.root.is_dir(), 'shared v3 drain root required')
        self.stream = (self.root / 'teardown.lock').open('a')
        deadline = self.now() + self.wait_seconds
        try:
            while True:
                self.check()
                require(self.now() < deadline, 'shared drain permit wait timed out')
                try:
                    fcntl.flock(self.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    self.sleep(.25)
            path = self.root / 'teardown-state.json'
            prior = json.loads(path.read_text()) if path.exists() else {}
            if prior.get('boot_id') == self.boot:
                require(prior.get('drained') is True, 'previous shared drain incomplete')
                until = prior['completed_monotonic'] + 60.0
                while self.now() < until:
                    self.check()
                    require(self.now() < deadline, 'shared drain cooldown timed out')
                    self.sleep(max(0.0, min(.25, until - self.now())))
            self.record = dict(boot_id=self.boot, output=str(self.output), pid=os.getpid(),
                               started_monotonic=self.now(), drained=False,
                               scope='whole chain window; includes autonomous fixture exits')
            if self.reservation is not None:
                self.record['chain_reservation'] = dict(self.reservation)
            atomic_json(path, self.record)
            return self
        except BaseException:
            self.stream.close()
            self.stream = None
            raise

    def complete(self):
        require(self.stream is not None and self.record is not None, 'drain permit not held')
        self.record.update(drained=True, completed_monotonic=self.now())
        atomic_json(self.root / 'teardown-state.json', self.record)

    def __exit__(self, kind, value, trace):
        if self.stream is not None:
            self.stream.close()
            self.stream = None


def screen_teardown_admit(lane, *, root=DEFAULT_DRAIN_ROOT, coordination_root=DEFAULT_ROOT,
                          proc=Path('/proc')):
    """Future B wrapper may COMPUTE under a proven live A exactness permit.

    The unmodified actual v3 Teardown still waits on the shared lock and its
    60-second gap. Stale/incomplete drains never gain this exception. This
    function replaces ONLY the prelaunch check in a newly sealed wrapper.
    """
    # Freeze active-marker removal while inspecting a live A permit. A normal
    # completion can otherwise remove A between the drain and marker reads.
    with (Path(coordination_root) / 'protocol.lock').open('r+') as gate:
        deadline = time.monotonic() + 30
        while True:
            try:
                fcntl.flock(gate, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                require(time.monotonic() < deadline, 'screen coordination snapshot timed out')
                time.sleep(.05)
        return _screen_teardown_admit_locked(lane, Path(root), Path(coordination_root), proc)


def _screen_teardown_admit_locked(lane, root, coordination_root, proc):
    path = root / 'teardown-state.json'
    if not path.exists():
        return
    row = json.loads(path.read_text())
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if row.get('boot_id') != boot or row.get('drained') is True:
        return
    require(lane == 'B', 'incomplete teardown; only registered B may overlap a live A window')
    owner = row.get('chain_reservation', {})
    active_a = json.loads((Path(coordination_root) / 'active-lane-A.json').read_text())
    active_b = json.loads((Path(coordination_root) / 'active-lane-B.json').read_text())
    require(owner == active_a and owner.get('scope') == 'lane-A'
            and owner.get('lane') == 'A' and owner.get('boot_id') == boot,
            'shared drain is not this live A exactness reservation')
    require(owner.get('start_ticks') is not None and
            process_identity(owner['pid'], proc) == owner['start_ticks'],
            'shared drain owner gone or PID reused')
    require(active_b.get('pid') == os.getpid() and active_b.get('start_ticks') is not None
            and process_identity(os.getpid(), proc) == active_b['start_ticks']
            and active_b.get('boot_id') == boot and active_b.get('lane') == 'B',
            'B screen has no matching live reservation')
    for lock in (root / 'teardown.lock', coordination_root / 'lane-A.lock',
                 coordination_root / 'lane-B.lock'):
        with lock.open('r+') as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                continue
            fcntl.flock(stream, fcntl.LOCK_UN)
            # Normal completion may race this read: its drained state is safe.
            require(json.loads(path.read_text()).get('drained') is True,
                    'shared drain reservation is not locked; coordinator required')
            return
