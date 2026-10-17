"""Bound CPU preparation to the owner-approved cores and new packet storage."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import shutil
HERE = Path(__file__).resolve().parent

def limits(planned_write_bytes=0):
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19, 'nice19 required'
    affinity = sorted(os.sched_getaffinity(0))
    assert set(affinity) <= set(range(4,16)) | set(range(20,32)), 'CPU affinity outside approved cores'
    used = sum(p.stat().st_size for p in (HERE/'build').rglob('*') if p.is_file())
    assert used + planned_write_bytes < 500_000_000, 'packet53b 500 MB build cap'
    free = shutil.disk_usage(HERE).free
    assert free - planned_write_bytes >= 18_000_000_000, 'preserve other packets storage reserve'
    return dict(nice=19, affinity=affinity, build_bytes=used, free_bytes=free,
                planned_write_bytes=planned_write_bytes)

@contextmanager
def exclusive_cpu_work(planned_write_bytes=0):
    (HERE/'build').mkdir(exist_ok=True)
    with (HERE/'build/cpu-work.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield limits(planned_write_bytes)
