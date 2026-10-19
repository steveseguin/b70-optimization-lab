"""Local CPU-only limits used by the shared compiler-turn guard."""
import os
from pathlib import Path
import shutil


def limits():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    assert shutil.disk_usage(Path(__file__).parent).free >= 27_000_000_000
