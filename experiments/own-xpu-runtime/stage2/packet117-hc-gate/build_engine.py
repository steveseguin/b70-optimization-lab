"""CPU-only packet117 resource guards; importing this module sets no caps."""
import os
import resource
import shutil
from pathlib import Path

P = Path(__file__).resolve().parent

def limits():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    assert shutil.disk_usage(P).free >= 25_000_000_000, 'root free below 25 GB'
    assert sum(f.stat().st_size for f in P.rglob('*') if f.is_file() and 'build' in f.relative_to(P).parts and not f.is_symlink()) <= 250_000_000
    resource.setrlimit(resource.RLIMIT_AS, (8*1024**3, 8*1024**3))
