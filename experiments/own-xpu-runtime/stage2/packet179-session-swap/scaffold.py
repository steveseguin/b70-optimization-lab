"""One-time private copy from frozen packet165 one-card; binary NOT inherited.

packet179 recompiles the entry TU (main.cpp + new checkpoint.hpp) and relinks
packet165's byte-identical kernel objects, so build/device is excluded here;
build_checkpoint.py produces the new binary with sha-asserted reused objects.
"""
import hashlib,json,shutil,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
OLD=P.parent/'packet165-warm-prefill'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(v,indent=2)+'\n')
old=OLD/'one-card';new=P/'one-card'
assert not new.exists(),'one-time scaffold refuses overwrite'
files=subprocess.check_output(['git','ls-files',str(old.relative_to(ROOT))],cwd=ROOT,text=True).splitlines()
copied={}
for rel in files:
    f=ROOT/rel;leaf=f.relative_to(old)
    if 'evidence' in leaf.parts or '__pycache__' in leaf.parts:continue
    if f.name in ('seal.json','READY-FOR-DEVICE.json','READY.json'):continue
    if leaf.parts[:2]==('build','device'):continue
    dest=new/leaf;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
    copied[str(leaf)]=sha(f)
save(new/'evidence/copy-baseline.json',dict(passed=True,files=copied,
    parent_binary_sha256=sha(old/'build/device/own-rt-iq3'),binary_copied=False,device_executed=False))
for leaf in ('build.json','identity-check.json','preparation-probe.json'):
    shutil.copy2(old/'evidence'/leaf,new/'evidence'/('parent-'+leaf))
for f in new.glob('*.py'):
    f.write_text(f.read_text().replace('packet165-warm-prefill','packet179-session-swap'))
for f in (new/'inputs').rglob('input.json'):
    f.write_text(f.read_text().replace('packet165-warm-prefill','packet179-session-swap'))
print('Copied packet165 one-card profile without the binary; READY absent.')
