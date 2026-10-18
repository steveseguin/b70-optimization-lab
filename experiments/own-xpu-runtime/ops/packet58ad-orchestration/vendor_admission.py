"""Relocate the inherited admission's metadata inputs, preserving original bytes."""
import hashlib,json,os,resource,shutil,sys
from pathlib import Path
R=Path(__file__).resolve().parents[4]
P=R/'experiments/own-xpu-runtime/stage2/packet58ad-onecard-record'
Z=P.parent/'packet58z-onecard-record'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    sys.path.insert(0,str(R/'experiments/own-xpu-runtime/ops/lane-queue'))
    import pin_guard
    pins,_=pin_guard.collect_pins(P)
    copied={}
    for path,digest,manifest in pins:
        if path.is_relative_to(Z/'lineage/owned-inputs'):
            assert path.suffix in ('.json','.jsonl','.py','.cpp','.hpp'),path
            assert sha(path)==digest
            dest=P/path.relative_to(Z);dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,dest);assert sha(dest)==digest
            copied[str(dest.relative_to(R))]=digest
    before={}
    for p in (P/'host-admission').rglob('*.json'):
        if p.name=='seal.json':continue
        raw=p.read_text();new=raw.replace(str(Z.relative_to(R)),str(P.relative_to(R)))
        if raw!=new:
            before[str(p.relative_to(P))]=sha(p);p.write_text(new)
    seal=P/'host-admission/seal.json';row=json.loads(seal.read_text())
    row['files']={n:sha(seal.parent/n) for n in row['files']}
    seal.write_text(json.dumps(row,indent=2,sort_keys=True)+'\n')
    (P/'lineage/admission-relocation.json').write_text(json.dumps(dict(
        original_packet=str(Z.relative_to(R)),original_metadata_sha256=before,
        copied_inputs=copied,raw_input_bytes_unchanged=True,admission_amounts_unchanged=True),indent=2)+'\n')
    print('Vendored',len(copied),'admission metadata inputs; no model/full-shape payload reads')
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
