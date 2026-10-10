"""Packet121 CPU scheduling helpers. No torch/device API; bounded memory and waits."""
import hashlib
import os
from pathlib import Path
import stat
import threading
import time

DISPLAY_SCHEDULES = ('sampler-a', 'sampler-b', 'eager-display')


def launch_options(env=None):
    env = os.environ if env is None else env
    display = env.get('LTX_DISPLAY_SCHEDULE', 'sampler-a')
    ahead = env.get('LTX_ANCHOR_READ_AHEAD', '0')
    if display not in DISPLAY_SCHEDULES or ahead not in ('0', '1'):
        raise ValueError('Invalid packet121 display schedule or anchor read-ahead')
    snapshot = env.get('LTX_SNAPSHOT_SCHEDULE', 'full')
    if snapshot not in ('full', 'a-xpu3-sync'):
        raise ValueError('Invalid packet121 snapshot schedule')
    if snapshot != 'full' and env.get('LTX_SNAPSHOT_MODE', 'fingerprint') != 'fingerprint':
        raise ValueError('a-xpu3-sync requires fingerprint snapshots')
    return display, int(ahead), snapshot


class SuccessorBarrier:
    """Events name the actual consuming request and source run, never just a global counter."""
    def __init__(self):
        self.condition = threading.Condition()
        self.events = {}

    def mark(self, source, anchor_sha, consumer, prompt_id, ns):
        with self.condition:
            self.events[(source, anchor_sha)] = dict(source_run_name=source, anchor_sha256=anchor_sha,
                consumer_run_name=consumer, prompt_id=prompt_id, sampler_b_start_ns=ns)
            while len(self.events) > 16:
                del self.events[next(iter(self.events))]
            self.condition.notify_all()

    def wait(self, source, anchor_sha, deadline, halted):
        started = time.monotonic()
        with self.condition:
            while True:
                event = self.events.get((source, anchor_sha))
                if halted():
                    reason = 'halted'
                    break
                if event is not None:
                    reason = 'matching-successor-sampler-b-start'
                    break
                left = deadline - time.monotonic()
                if left <= 0:
                    reason = 'bound'
                    break
                self.condition.wait(min(left, 0.05))
        return dict(reason=reason, waited_s=round(time.monotonic() - started, 6),
                    event=event, released_ns=time.time_ns())


def _identity(path):
    # Match the native provider's path and file checks even on a cache hit.
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Unsafe anchor path')
    s = path.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1:
        raise ValueError('Anchor file must be regular and single-link')
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)


class AnchorReadAhead:
    """One immutable verified CPU frame, opportunistic: a racing consumer uses the native reader.

    A hit retains per-request SHA and file identity checks. The native reader performs finiteness
    once on preparation; immutable bytes cannot gain a nonfinite word after that check.
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.entry = None

    def prepare(self, path, sha, read):
        before = _identity(path)
        raw = read(path, sha)
        if type(raw) is not bytes or before != _identity(path) or hashlib.sha256(raw).hexdigest() != sha:
            raise ValueError('Anchor changed during read-ahead')
        with self.lock:
            self.entry = (str(path), sha, before, raw)
        return dict(path=str(path), sha256=sha, bytes=len(raw), prepared_ns=time.time_ns())

    def take(self, path, sha, read):
        with self.lock:
            entry = self.entry
        if entry is None or entry[:2] != (str(path), sha):
            return read(path, sha), 'native-miss'
        before = _identity(path)
        if before != entry[2]:
            return read(path, sha), 'native-file-changed'
        raw = entry[3]
        if hashlib.sha256(raw).hexdigest() != sha or before != _identity(path):
            raise ValueError('Cached anchor changed during consume')
        return raw, 'verified-read-ahead'
