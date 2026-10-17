"""CPU-only bounded work policy; no services, payloads or device discovery."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import shutil
HERE=Path(__file__).resolve().parent
def limits(planned_write_bytes=256_000_000):
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    affinity=sorted(os.sched_getaffinity(0))
    assert set(affinity)<=set(range(4,16))|set(range(20,32))
    free=shutil.disk_usage(HERE).free
    assert free-planned_write_bytes>=8_000_000_000
    return dict(nice=19,affinity=affinity,free_bytes=free,planned_write_bytes=planned_write_bytes)
@contextmanager
def exclusive_cpu_work(planned_write_bytes=256_000_000):
    with (HERE/'build/cpu-work.lock').open('a') as f:
        fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield limits(planned_write_bytes)
