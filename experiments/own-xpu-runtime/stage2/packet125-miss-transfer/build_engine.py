"""CPU build bounds; imports never change resource limits."""
import hashlib,os,shutil
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert shutil.disk_usage('/').free>=25_000_000_000,'root below 25 GB'
 assert sum(f.stat().st_size for f in (P/'build').rglob('*') if f.is_file())<=200_000_000,'build exceeds 200 MB'
