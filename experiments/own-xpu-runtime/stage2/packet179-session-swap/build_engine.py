"""Shared packet179 helpers: paths, hashing, receipts, limits, compiler turn.

packet179 recompiles only the entry TU (adapt_native.py delta) and relinks
packet165's byte-identical kernel objects via build_checkpoint.py.
"""
import hashlib,importlib.util,json,os,resource,shutil
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];STAGE=P.parent

def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,r):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(r,indent=2)+'\n')
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert shutil.disk_usage(P).free>=27_000_000_000,'CPU stop: 27 GB'
def turn():
 spec=importlib.util.spec_from_file_location('packet163_compile_turn',ROOT/'experiments/own-xpu-runtime/ops/compile_turn.py')
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m.turn()
