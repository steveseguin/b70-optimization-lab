"""CPU-only host watchdog; never sends a signal except through the one-shot owner.

Pressure is MemTotal - MemAvailable, not summed RSS/cgroup usage (which aliases
pinned and file pages). A missing sample fails closed. No torch or GPU queries.
"""
import json
import os
from pathlib import Path
import threading
import time

GIB = 2**30
PRESSURE_LIMIT = 80_000_000_000
AVAILABLE_FLOOR = 32 * GIB
INTERVAL = 0.250


def sample_memory(path=Path('/proc/meminfo')):
    fields = {}
    for line in path.read_text().splitlines():
        key, value = line.split(':', 1)
        if key in ('MemTotal', 'MemAvailable'):
            fields[key] = int(value.split()[0]) * 1024
    total, available = fields['MemTotal'], fields['MemAvailable']
    if not 0 <= available <= total:
        raise ValueError('Invalid MemAvailable/MemTotal')
    return {'monotonic': time.monotonic(), 'mem_total_bytes': total,
            'mem_available_bytes': available,
            'accounted_pressure_bytes': total - available}


def trip_reason(sample, next_bytes=0):
    if next_bytes < 0:
        raise ValueError('negative allocation')
    if sample['accounted_pressure_bytes'] + next_bytes >= PRESSURE_LIMIT:
        return 'whole-host pressure >= 80 GB'
    if sample['mem_available_bytes'] - next_bytes <= AVAILABLE_FLOOR:
        return 'MemAvailable <= 32 GiB'
    return None


def process_identity(pid=None):
    pid = os.getpid() if pid is None else pid
    # comm may contain spaces or parentheses; starttime is field 22.
    fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    return {'pid': pid, 'starttime_ticks': int(fields[19])}


class MemoryWatchdog:
    def __init__(self, run, request_stop, sampler=sample_memory, *,
                 threshold=trip_reason, interval=INTERVAL):
        self.run = Path(run)
        self.request_stop = request_stop
        self.sampler = sampler
        self.threshold = threshold
        self.interval = interval
        self.done = threading.Event()
        self.tripped = threading.Event()
        self.reason = None
        self.thread = None
        self.check_lock = threading.Lock()

    def check(self):
        with self.check_lock:
            return self._check()

    def _check(self):
        try:
            sample = self.sampler()
            reason = self.threshold(sample)
        except Exception as exc:
            sample = {'monotonic': time.monotonic(), 'error': str(exc)}
            reason = 'host memory observation unavailable'
        try:
            with (self.run / 'host-memory-samples.jsonl').open('a') as out:
                out.write(json.dumps(sample) + '\n')
        except OSError as exc:
            reason = 'host memory receipt unavailable'
            sample['receipt_error'] = str(exc)
        if reason and not self.tripped.is_set():
            self.reason = reason
            self.tripped.set()
            try:
                (self.run / 'memory-watchdog-event.json').write_text(json.dumps({
                    'reason': reason, 'sample': sample, 'interval_seconds': self.interval,
                    'controller': process_identity(), 'action': 'latch cancellation; one SIGINT',
                }, indent=2) + '\n')
            finally:
                # A full disk or inaccessible /proc must never disable cancellation.
                self.request_stop(reason)
        return reason

    def start(self):
        def watch():
            while not self.done.is_set():
                tick = time.monotonic()
                try:
                    self.check()
                except Exception as exc:
                    self.reason = f'watchdog failure: {exc}'
                    self.tripped.set()
                    self.request_stop(self.reason)
                    return
                self.done.wait(max(0, self.interval - (time.monotonic() - tick)))
        self.thread = threading.Thread(target=watch, name='host-memory-watchdog', daemon=True)
        self.thread.start()

    def close(self):
        self.done.set()
        if self.thread:
            self.thread.join(timeout=2)
