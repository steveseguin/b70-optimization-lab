"""Passive imports only; runtime identity and canonical oracle remain sealed."""
import hashlib,json
from pathlib import Path
import oracle as D
import suite_metrics as METRICS
import p56_head_support as SUPPORT
HERE=Path(__file__).resolve().parent
ROOT=next(p for p in HERE.parents if (p/'.git').is_dir())
S=SUPPORT.SUPERVISION
ARITHMETIC='iq3-p49-split32-v1'
def require(ok,message):
 if not ok:raise ValueError(message)
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,r):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(r,indent=2,allow_nan=False)+'\n')
