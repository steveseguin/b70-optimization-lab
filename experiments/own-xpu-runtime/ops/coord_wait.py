#!/usr/bin/env python3
"""Bounded coordinator waits. Importing this module has no operational effects.

Deadlines are absolute time.monotonic() values; offsets count complete JSONL
lines (zero means the beginning). wait_event returns the terminal event dict,
including refusals/failures; callers must check its event before queuing more.

    deadline = time.monotonic() + 300
    with hold(['B'], 'waiting for A smoke', deadline) as held:
        # Optional: held.freeze('codex-preparation.service')
        result = wait_event('A', name, offset, deadline)

A hold never freezes units implicitly. Its watchdog releases owned resources
at the deadline even if the body is blocked; it cannot cancel arbitrary body
code. Use the same deadline for waits and call held.check() before other work.
Exceptions (including KeyboardInterrupt) unwind normally. On the main thread,
SIGTERM also unwinds the hold and its previous handler is restored on exit.
SIGKILL/process death cannot run Python cleanup; supervisors must handle those.
No queue edits, driver restarts, GPU access, or external notifications.
"""
from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid


DIRECTORY = Path(__file__).resolve().parent / 'lane-queue'
TERMINAL = frozenset({'DONE', 'REPORT-FAILED', 'REFUSED-PREDEVICE',
                      'REFUSED-fast', 'FAILED', 'FAILED-status',
                      'FAILED-postflight', 'SKIPPED-DEPENDENCY'})


class DriverUnavailable(RuntimeError):
    pass


class CleanupError(RuntimeError):
    pass


def alert(message):
    """Local notification only; suitable for a coordinator's captured stderr."""
    print('ALERT: ' + message, file=sys.stderr, flush=True)


def _lane(lane):
    if lane not in ('A', 'B'):
        raise ValueError('lane must be A or B')
    return lane


def _remaining(deadline):
    if type(deadline) not in (int, float) or not math.isfinite(deadline):
        raise ValueError('deadline must be a finite absolute monotonic time')
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('coordinator deadline expired')
    return remaining


def ready(path):
    """Require a JSON boolean; an explicit ready_for_device overrides ready."""
    try:
        row = json.loads(Path(path).read_text())
        return isinstance(row, dict) and row.get('ready_for_device', row.get('ready')) is True
    except (OSError, ValueError):
        return False


def _systemctl(*args, timeout=5):
    return subprocess.run(['/usr/bin/systemctl', '--user', *args],
                          stdin=subprocess.DEVNULL, capture_output=True,
                          text=True, timeout=timeout, check=True)


def driver_alive(lane, *, timeout=5):
    """Report absence or an unreadable unit state; never restart a driver."""
    lane = _lane(lane)
    try:
        cp = _systemctl('list-units', '--state=active', '--plain', '--no-legend',
                        '--no-pager', f'lanequeue-{lane}*.service', timeout=timeout)
        for line in cp.stdout.splitlines():
            fields = line.split()
            if (len(fields) >= 3 and re.fullmatch(r'lanequeue-' + lane + r'[^\s]*\.service', fields[0])
                    and fields[2] == 'active'):
                return True
    except (OSError, subprocess.SubprocessError):
        alert(f'lane {lane}: driver state unavailable')
        return False
    alert(f'lane {lane}: no active lanequeue-{lane} unit')
    return False


def wait_event(lane, name, offset, deadline, *, directory=None, poll=1):
    """Wait from a complete-line offset, failing on deadline or driver death.

    Read terminal events before checking liveness: a driver may exit just after
    recording a failure. Partial trailing writes wait for their newline;
    malformed complete records and log replacement/truncation fail explicitly.
    """
    lane = _lane(lane)
    if not isinstance(name, str) or not name:
        raise ValueError('job name must be nonempty')
    if type(offset) is not int or offset < 0:
        raise ValueError('offset must be a nonnegative line count')
    if not math.isfinite(poll) or poll <= 0:
        raise ValueError('poll must be positive and finite')
    path = Path(directory or DIRECTORY) / f'events-{lane}.jsonl'
    stream = None
    identity = None
    try:
        while True:
            _remaining(deadline)
            if stream is None:
                try:
                    stream = path.open('rb')
                except FileNotFoundError:
                    pass
                if stream is not None:
                    stat = os.fstat(stream.fileno())
                    identity = (stat.st_dev, stat.st_ino)
                    for _ in range(offset):
                        if not stream.readline().endswith(b'\n'):
                            raise ValueError('event offset exceeds complete log lines')
            if stream is not None:
                stat = path.stat()
                if (stat.st_dev, stat.st_ino) != identity or stat.st_size < stream.tell():
                    raise ValueError('event log replaced or truncated while waiting')
                while True:
                    _remaining(deadline)
                    position = stream.tell()
                    line = stream.readline()
                    if not line.endswith(b'\n'):
                        stream.seek(position)
                        break
                    row = json.loads(line)
                    if not isinstance(row, dict):
                        raise ValueError('event must be a JSON object')
                    if (row.get('name') == name and row.get('lane', lane) == lane
                            and row.get('event') in TERMINAL):
                        return row
            if not driver_alive(lane, timeout=min(5, _remaining(deadline))):
                raise DriverUnavailable(f'lane {lane}: driver unavailable while waiting for {name}')
            time.sleep(min(poll, _remaining(deadline)))
    except TimeoutError:
        alert(f'lane {lane}: deadline waiting for {name}')
        raise
    finally:
        if stream is not None:
            stream.close()


class _Hold:
    def __init__(self, lanes, reason, deadline, directory):
        self.lanes = tuple(dict.fromkeys(_lane(lane) for lane in lanes))
        if not self.lanes or not isinstance(reason, str) or not reason.strip():
            raise ValueError('hold needs lanes and a nonempty reason')
        _remaining(deadline)
        self.directory = Path(directory or DIRECTORY)
        self.deadline = deadline
        self.text = f'coord_wait {uuid.uuid4().hex}: {reason}\n'
        self.pauses = []
        self.frozen = []
        self.mutex = threading.RLock()
        self.closed = False
        self.errors = []
        self.timer = None

    def check(self):
        _remaining(self.deadline)
        if self.closed:
            raise RuntimeError('hold already released')

    def acquire(self):
        with self.mutex:
            self.check()
            for lane in self.lanes:
                self.check()
                path = self.directory / f'PAUSE-{lane}'
                # Never overwrite another coordinator's pause, even same reason.
                # Publish complete text atomically; a failed write must not leave
                # an empty, unrecognizable pause that our cleanup cannot own.
                with tempfile.NamedTemporaryFile(mode='w', dir=self.directory,
                                                 prefix='.coord-wait-') as stream:
                    stream.write(self.text)
                    stream.flush()
                    os.fsync(stream.fileno())
                    self.pauses.append(path)
                    os.link(stream.name, path)
            self.timer = threading.Timer(_remaining(self.deadline), self._expire)
            self.timer.daemon = True
            self.timer.start()

    def freeze(self, unit):
        """Explicitly freeze one running Codex unit, remembering thaw ownership.

        Already-frozen units belong to someone else and are left untouched.
        Ambiguous state fails; a timed-out freeze is still thawed on exit.
        """
        if not isinstance(unit, str) or not re.fullmatch(r'codex[-A-Za-z0-9_.]*\.service', unit):
            raise ValueError('freeze requires an explicit codex*.service unit')
        with self.mutex:
            self.check()
            if unit in self.frozen:
                return True
            cp = _systemctl('show', unit, '--property=FreezerState', '--value',
                            timeout=min(5, _remaining(self.deadline)))
            state = cp.stdout.strip()
            if state == 'frozen':
                return False
            if state != 'running':
                raise RuntimeError(f'{unit}: ambiguous freezer state')
            self.check()
            # Register before the call: timeout may mean the freeze took effect.
            self.frozen.append(unit)
            _systemctl('freeze', unit, timeout=min(5, _remaining(self.deadline)))
            self.check()
            return True

    def _expire(self):
        alert('coordinator hold deadline expired; releasing owned resources')
        self.release()

    def release(self):
        with self.mutex:
            if self.closed:
                return
            self.closed = True
            if self.timer is not None:
                self.timer.cancel()
            # Try every cleanup even if another fails. Never retry services.
            for unit in reversed(self.frozen):
                try:
                    _systemctl('thaw', unit)
                except (OSError, subprocess.SubprocessError) as exc:
                    self.errors.append(f'could not thaw {unit}: {type(exc).__name__}')
            for path in reversed(self.pauses):
                try:
                    if path.read_text() == self.text:
                        path.unlink()
                except FileNotFoundError:
                    pass
                except (OSError, ValueError) as exc:
                    self.errors.append(f'could not release {path.name}: {type(exc).__name__}')
            for error in self.errors:
                alert(error)


@contextmanager
def hold(lanes, reason, deadline, *, directory=None):
    """Own PAUSE files until exit/deadline; yield an optional freeze/check handle.

    Existing pauses refuse acquisition. Unique text prevents cleanup from
    removing a replacement pause. All cooperating writers must avoid replacing
    another owner's pause during cleanup's read/unlink pair.
    """
    held = _Hold(lanes, reason, deadline, directory)
    def terminate(signum, frame):
        raise SystemExit(128 + signum)
    main_thread = threading.current_thread() is threading.main_thread()
    previous = signal.getsignal(signal.SIGTERM) if main_thread else None
    try:
        if main_thread:
            signal.signal(signal.SIGTERM, terminate)
        held.acquire()
        yield held
        held.check()
    finally:
        try:
            held.release()
        finally:
            if main_thread and signal.getsignal(signal.SIGTERM) is terminate:
                signal.signal(signal.SIGTERM, previous)
        if held.errors:
            raise CleanupError('; '.join(held.errors))
