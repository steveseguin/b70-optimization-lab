"""Copy forward only; never modify a source packet or dereference its links."""
import hashlib,json,os,shutil
from pathlib import Path
R=Path(__file__).resolve().parents[4]
S=R/'experiments/own-xpu-runtime/stage2'
P=S/'packet58aj-onecard-resident'
A=S/'packet58ah-onecard-record'
G=S/'packet58ag-onecard-ports'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def copy(src,dst):
    if src.is_dir():shutil.copytree(src,dst,symlinks=True,ignore=shutil.ignore_patterns('__pycache__'))
    else:dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst,follow_symlinks=False)
def main():
    assert not P.exists()
    assert shutil.disk_usage('/').free>30_350_000_000
    P.mkdir();(P/'evidence').mkdir();(P/'lineage').mkdir()
    originals={}
    for f in A.iterdir():
        if f.is_file() and f.name not in ('ready.json','build-receipt.json','submission-pins.json','queue.lock','window.lock'):
            copy(f,P/f.name);originals[f.name]=sha(f)
    for n in ('lineage','host-admission','screen-reader','selections'):
        if (P/n).exists():(P/n).rmdir()
        copy(A/n,P/n)
    # Historical model output is never copied into the new device evidence tree.
    for n in ('postload-census.json','58c-kd','fullshape-submit-cpu.json','postload-allocation-cpu.json','startup-cpu.json'):
        copy(A/'evidence'/n,P/'evidence'/n)
    for n in ('gnu-host/fullshape-submit','gnu-host/p58-cache-fixtures','device/p58-cache-fixtures'):
        copy(A/'build'/n,P/'build'/n)
    # Private bracket harness, retaining its original module boundaries.
    Q=P/'screen';Q.mkdir();(Q/'evidence').mkdir()
    for f in G.iterdir():
        if f.is_file() and f.suffix in ('.py','.json','.txt') and f.name not in ('READY-FOR-DEVICE.json','build-receipt.json','immutable-inputs.json','copy-manifest.json'):
            copy(f,Q/f.name)
    for n in ('selections','host-admission'):
        (Q/n).symlink_to('../'+n,target_is_directory=True)
    (Q/'build').symlink_to('../build',target_is_directory=True)
    # Source and object closure used by the exact 58ah engine (58ag).
    for n in ('native','frozen-inputs'):
        copy(G/n,P/n)
    copy(G/'build/native',P/'build/native')
    commands=json.loads((G/'evidence/build.json').read_text())['commands']
    for row in commands:
        for arg in row['command']:
            f=Path(arg)
            if arg.endswith('.o') and f.is_file() and f.is_relative_to(G/'build'):
                dest=P/f.relative_to(G)
                if not dest.exists():copy(f,dest)
    (P/'lineage/58ag-build-commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    for n in ('resident_lookup.hpp','resident_weights.hpp','resident_cpu.cpp'):
        copy(S/'packet58t-resident-lookups/native'/n,P/'native'/n)
    copy(S/'packet58t-resident-lookups/resident_source.py',P/'resident_source.py')
    # Relocate active files, leaving historical snapshots as captured evidence.
    for f in P.rglob('*'):
        if f.is_symlink() or not f.is_file() or 'lineage' in f.relative_to(P).parts:continue
        if f.suffix not in ('.py','.json','.cpp','.hpp','.h','.txt','.d'):continue
        raw=f.read_text()
        raw=raw.replace(str(A),str(P)).replace('packet58ah-onecard-record','packet58aj-onecard-resident')
        raw=raw.replace(str(G),str(P)).replace('packet58ag-onecard-ports','packet58aj-onecard-resident')
        raw=raw.replace('packet58-onecard-58ah-b','packet58-onecard-58aj-a').replace('card0-58ah-b','card0-58aj-a').replace('fault-review-58ah-b','fault-review-58aj-a')
        raw=raw.replace('proposed-p58ag-','proposed-p58aj-').replace('packet58ag-', 'packet58aj-')
        if f.is_relative_to(Q):
            raw=raw.replace('P.parents[3]','P.parents[4]').replace('HERE.parents[3]','HERE.parents[4]')
            raw=raw.replace('HERE.parent /','HERE.parents[1] /').replace('P.parent /','P.parents[1] /')
            raw=raw.replace("parents[2] / 'ops/", "parents[3] / 'ops/")
        f.write_text(raw)
    (P/'lineage/template-58ah.json').write_text(json.dumps(dict(source=str(A.relative_to(R)),original_files=originals,symlinks_preserved=True),indent=2)+'\n')
    # Keep the sealed admission bundle internally consistent after path relocation.
    seal=P/'host-admission/seal.json';v=json.loads(seal.read_text())
    v['files']={n:sha(seal.parent/n) for n in v['files']};seal.write_text(json.dumps(v,indent=2)+'\n')
    print('Copied 58ah chain and 58ag engine/bracket; parents untouched')
if __name__=='__main__':main()
