"""CPU preparation helpers; importing this module never changes resource limits."""
import hashlib
import os
from pathlib import Path
import shutil
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19,'CPU work requires nice19'
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32)),'CPU affinity'
 assert shutil.disk_usage('/').free>=25_000_000_000,'root free below25GB'
 size=sum(f.stat().st_size for folder in (P/'build',P/'v5/build') for f in folder.rglob('*') if f.is_file() and not f.is_symlink())
 assert size<=250_000_000,('packet build exceeds250MB',size)
