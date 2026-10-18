"""Packet58j bounded CPU compiler admission; no device execution."""
import os,resource,shutil
from pathlib import Path
P=Path(__file__).resolve().parent
B=P/'build'
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert shutil.disk_usage(P).free>=2_000_000_000
 assert sum(f.stat().st_size for f in B.rglob('*') if f.is_file())<=300_000_000
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
