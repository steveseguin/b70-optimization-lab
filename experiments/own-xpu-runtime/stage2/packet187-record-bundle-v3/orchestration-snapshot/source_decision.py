"""Shared packet187 paths; policy is fixed in policy187.json."""
import hashlib,json
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3];P=ROOT/'experiments/own-xpu-runtime/stage2/packet187-record-bundle-v3'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
