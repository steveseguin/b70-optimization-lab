"""Shared CPU preparation limits. Does not inspect or initialize any device."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import os
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
NOT_BEFORE = datetime(2026, 10, 17, 2, 55, tzinfo=timezone.utc)
CPU_SET = set(range(4, 16)) | set(range(20, 32))
MIN_DISK_FREE = 8_000_000_000


def limits(*, now=None, heavy=True, planned_write_bytes=0):
    current = datetime.now(timezone.utc) if now is None else now
    if heavy and current < NOT_BEFORE:
        raise ValueError('builds and sustained CPU work prohibited before 2026-10-17T02:55:00Z')
    if os.getpriority(os.PRIO_PROCESS, 0) != 19:
        raise ValueError('preparation requires nice -n 19')
    affinity = set(os.sched_getaffinity(0))
    if not affinity or not affinity <= CPU_SET:
        raise ValueError('preparation requires taskset -c 4-15,20-31 (or a subset)')
    free = shutil.disk_usage(HERE).free
    if planned_write_bytes < 0 or free - planned_write_bytes < MIN_DISK_FREE:
        raise ValueError('planned writes would breach the unchanged 8 GB packet storage floor')
    return dict(checked_utc=current.isoformat(), not_before_utc=NOT_BEFORE.isoformat(),
                nice=19, affinity=sorted(affinity), disk_free_bytes=free,
                planned_write_bytes=planned_write_bytes, min_remaining_bytes=MIN_DISK_FREE)


@contextmanager
def exclusive_cpu_work(*, planned_write_bytes=0):
    """Refuse overlapping packet46 builds/benchmarks; never queue or retry."""
    receipt = limits(planned_write_bytes=planned_write_bytes)
    build = HERE / 'build'
    build.mkdir(exist_ok=True)
    with (build / 'cpu-work.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('another packet46 CPU build/benchmark owns the preparation slot') from error
        yield receipt
