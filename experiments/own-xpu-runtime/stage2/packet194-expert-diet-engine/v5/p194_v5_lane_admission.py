"""Cooperative, crash-closed file protocol for future sealed chains/screens.

No subprocesses, signals, service operations or device opens. All participants
must use one shared root. Existing sealed runners do not understand this
protocol and must not overlap a timing window.
"""
from contextlib import contextmanager
import fcntl
import json
import math
import os
from pathlib import Path
import time
import uuid

from p194_v5_chain_devices import require, process_identity

DEFAULT_ROOT = Path('/home/steve/own-xpu-runtime-results/coordination/chain-lanes-v1')
EXACT_WINDOWS = frozenset(('screen', 'K0', 'K1a', 'K1b', 'K2', 'KD', 'W0p', 'WS',
                           'WS64x', 'WS128x', 'W2m-exact'))
TIMING_WINDOWS = frozenset(('WS128', 'WS64', 'WSs', 'W2m', 'W2m-speed', 'W2mc',
                            'W2s', 'W2n', 'W2x', 'W2d', 'W2c'))


def window_scope(window, *, timing_claim=False):
    require(window in EXACT_WINDOWS | TIMING_WINDOWS, 'unregistered window policy')
    # A new timing use can upgrade an exactness window, never downgrade speed.
    return 'whole-host' if timing_claim or window in TIMING_WINDOWS else 'lane-A'


def admission_scope(lane, window, *, timing_claim=False):
    require(lane in ('A', 'B'), 'unknown lane')
    return window_scope(window, timing_claim=timing_claim) if lane == 'A' else 'lane-B'


def present(path):
    # A damaged/dangling coordination marker also means stop, not permission.
    return path.exists() or path.is_symlink()


def atomic_json(path, row):
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('x') as stream:
            json.dump(row, stream, sort_keys=True, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class Reservation:
    """A window or one complete lane-B screen, including drain and postflight.

    A creates hold-lane-B BEFORE waiting for B's current lease. B checks the
    flag and acquires its lease under the SAME protocol.lock. Thus either B
    is already admitted (A waits), or B cannot launch until A releases.

    Context exit only closes locks. Explicit complete(drained=True) removes
    owned markers. Exceptions, timeout, interruption and process death leave
    durable markers; no automatic stale-PID deletion or retry is allowed.
    """
    def __init__(self, lane, *, window='screen', root=DEFAULT_ROOT, wait_seconds=1800,
                 timing_claim=False, check=lambda: None, now=time.monotonic,
                 sleep=time.sleep):
        require(lane in ('A', 'B'), 'unknown lane')
        require(math.isfinite(wait_seconds) and 0 < wait_seconds <= 7200, 'bounded wait required')
        self.lane, self.window, self.root = lane, window, Path(root)
        self.scope = admission_scope(lane, window, timing_claim=timing_claim)
        self.wait_seconds, self.check, self.now, self.sleep = wait_seconds, check, now, sleep
        self.files, self.entered, self.completed = [], False, False
        self.hold = self.root / 'hold-lane-B'
        self.active = self.root / ('active-lane-' + lane + '.json')
        self.record = dict(schema='own-runtime.chain-lanes.v1', token=uuid.uuid4().hex,
                           lane=lane, window=window, scope=self.scope, pid=os.getpid(),
                           start_ticks=process_identity(os.getpid()),
                           boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())

    def _open_lock(self, name):
        fd = os.open(self.root / name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        return os.fdopen(fd, 'r+')

    def _tick(self):
        self.check()
        require(self.now() < self.deadline, 'coordination wait timed out; markers retained')

    def _try_lock(self, stream):
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            return False

    @contextmanager
    def _gate(self):
        with self._open_lock('protocol.lock') as stream:
            while not self._try_lock(stream):
                self._tick()
                self.sleep(.05)
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    def __enter__(self):
        require(not self.entered and not self.files, 'reservation cannot be reused')
        self.deadline = self.now() + self.wait_seconds
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        stat = self.root.lstat()
        require(not self.root.is_symlink() and self.root.is_dir() and stat.st_uid == os.getuid()
                and stat.st_mode & 0o022 == 0, 'coordination root must be private, owned, real directory')
        try:
            while True:
                self._tick()
                with self._gate():
                    if self.lane != 'B' or not present(self.hold):
                        require(not present(self.active), 'active marker requires coordinator review: ' + str(self.active))
                        if self.lane == 'A':
                            require(not present(self.hold), 'hold requires coordinator review')
                        stream = self._open_lock('lane-' + self.lane + '.lock')
                        self.files.append(stream)
                        require(self._try_lock(stream), 'lane already reserved')
                        self.record['started_monotonic'] = self.now()
                        atomic_json(self.active, self.record)
                        if self.scope == 'whole-host':
                            atomic_json(self.hold, self.record)
                        break
                self.sleep(.25)  # B pauses BETWEEN screens, never interrupts one
            if self.scope == 'whole-host':
                stream = self._open_lock('lane-B.lock')
                self.files.append(stream)
                while not self._try_lock(stream):
                    self._tick()
                    self.sleep(.25)
                # A crashed B releases flock but leaves this marker behind.
                require(not present(self.root / 'active-lane-B.json'),
                        'lane B did not confirm drain; marker retained')
            self.entered = True
            return self
        except BaseException:
            self._close()
            raise

    def complete(self, *, drained):
        require(self.entered and not self.completed and drained is True,
                'explicit completed drain and postflight required')
        # Completion is not subject to the START wait deadline. A screen can
        # legitimately run longer; still honor the caller's stop/fault checks.
        self.deadline = self.now() + self.wait_seconds
        with self._gate():
            paths = [self.active] + ([self.hold] if self.scope == 'whole-host' else [])
            for path in paths:
                require(json.loads(path.read_text()).get('token') == self.record['token'],
                        'coordination owner changed; never remove another owner marker')
            for path in paths:
                path.unlink()
            self.completed = True
            # Publish availability and release flock under the same gate. A
            # waiter must not see a missing flag with the lane still locked.
            self._close()

    def _close(self):
        for stream in reversed(self.files):
            stream.close()
        self.files = []

    def __exit__(self, kind, value, trace):
        self._close()


def lane_b_screen(**kwargs):
    """Acquire before calling the existing v3 screen entry; one screen per lease."""
    return Reservation('B', **kwargs)
