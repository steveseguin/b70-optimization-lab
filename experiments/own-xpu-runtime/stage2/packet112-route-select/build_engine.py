"""CPU-only build helpers. Importing this module never applies resource limits."""
import hashlib, json, os, resource
from pathlib import Path
P = Path(__file__).resolve().parent
ROOT = P.parents[3]
B = P / 'build'
BASE = P.parent / 'packet97-record-bundle'
def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()
def save(p, value):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(value, indent=2) + '\n')
def limits():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8,16)) | set(range(24,32))
    resource.setrlimit(resource.RLIMIT_AS, (8*1024**3, 8*1024**3))
