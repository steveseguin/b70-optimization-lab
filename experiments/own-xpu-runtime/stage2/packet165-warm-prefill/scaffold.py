"""One-time private copy from frozen packet163; no native code changes."""
import hashlib,json,shutil,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
OLD=P.parent/'packet163-full-gate'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(v,indent=2)+'\n')
for name in ('one-card','two-card'):
    old=OLD/name;new=P/name
    assert not new.exists(),'one-time scaffold refuses overwrite'
    files=subprocess.check_output(['git','ls-files',str(old.relative_to(ROOT))],cwd=ROOT,text=True).splitlines()
    copied={}
    for rel in files:
        f=ROOT/rel;leaf=f.relative_to(old)
        if 'evidence' in leaf.parts or f.name in ('seal.json','READY-FOR-DEVICE.json','READY.json'):continue
        dest=new/leaf;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
        copied[str(leaf)]=sha(f)
    # Keep the exact executable, including its embedded frozen constant paths.
    binary=old/'build/device/own-rt-iq3';dest=new/'build/device/own-rt-iq3'
    dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(binary,dest)
    dependencies={str((old/r['local']).relative_to(ROOT)):r['sha256'] for r in json.loads((old/'runtime-constants.json').read_text())}
    save(new/'inherited-native.json',dict(parent=str(old.relative_to(ROOT)),binary_sha256=sha(binary),embedded_readonly_dependencies=dependencies,native_recompiled=False))
    save(new/'evidence/copy-baseline.json',dict(passed=True,files=copied,binary_sha256=sha(binary),device_executed=False))
    for leaf in ('build.json','identity-check.json','preparation-build.json','preparation-probe.json'):
        shutil.copy2(old/'evidence'/leaf,new/'evidence'/('parent-'+leaf))
    # Runtime Python paths must point into this packet; native/lineage are frozen.
    for f in new.glob('*.py'):
        f.write_text(f.read_text().replace('packet163-full-gate','packet165-warm-prefill'))
for leaf in ('build_engine.py','package_rows.py','check_queue_rows.py','probe_imports.py','test_measurement.py','test_report512.py','validate_flags.py'):
    text=(OLD/leaf).read_text().replace('packet163-full-gate','packet165-warm-prefill').replace('proposed-p163-','proposed-p165-').replace("name=f'packet163-","name=f'packet165-")
    (P/leaf).write_text(text)
(P/'evidence').mkdir(exist_ok=True)
shutil.copy2('/tmp/packet165-dnr.txt',P/'evidence/do-not-repeat-prefill-batch.txt')
print('Copied frozen sources and exact native binaries; READY absent.')
