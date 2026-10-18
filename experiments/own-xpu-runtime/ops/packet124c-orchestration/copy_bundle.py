"""Copy packet124b without dereferencing links; restore packet103/97 aliases."""
import hashlib,json,os,shutil
from pathlib import Path
ROOT=Path('/home/steve/llm-optimizations');BASE=ROOT/'experiments/own-xpu-runtime'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def links(root):return {str(p.relative_to(root)):os.readlink(p) for p in root.rglob('*') if p.is_symlink()}
def copy_bundle():
 assert shutil.disk_usage('/').free>=25_000_000_000
 src=BASE/'stage2/packet124b-record-bundle';dst=BASE/'stage2/packet124c-record-bundle'
 ops=BASE/'ops/packet124c-orchestration';assert not dst.exists() and not ops.exists()
 def ignore(path,names):return [n for n in names if n=='__pycache__' or n.startswith('device-cards01-')]
 shutil.copytree(src,dst,symlinks=True,ignore=ignore)
 shutil.copytree(BASE/'ops/packet124b-orchestration',ops,symlinks=True,ignore=ignore)
 before=links(src);audit=[];restored={}
 for packet in ('packet103-record-bundle','packet97-record-bundle'):
  ref=BASE/'stage2'/packet
  for name,target in links(ref).items():
   dest=dst/name;old=src/name
   row=dict(reference=packet,path=name,target=target)
   if old.exists() and not old.is_symlink():
    if name not in restored:
     if old.is_file():assert sha(old)==sha(ref/name),name
     if dest.is_dir():shutil.rmtree(dest)
     else:dest.unlink()
     dest.symlink_to(target);restored[name]=target
    row['status']='restored-byte-identical' if old.is_file() else 'restored-authority'
   elif not old.exists():row['status']='absent-historical-scratch-not-copied'
   else:row['status']='preserved-existing-link'
   audit.append(row)
 for name,target in before.items():
  if name.startswith('oracle/') or name.startswith('build/device-cards01-'):continue
  assert (dst/name).is_symlink() and os.readlink(dst/name)==target,name
 binaries={str(f.relative_to(src)):sha(f) for f in (src/'build/device/own-rt-iq3',src/'build/gnu-host/own-rt-iq3')}
 for name,digest in binaries.items():assert sha(dst/name)==digest
 (ops/'inputs/symlink-audit.json').write_text(json.dumps(dict(passed=True,device_executed=False,source=str(src.relative_to(ROOT)),references=audit,restored=restored,binaries=binaries),indent=2)+'\n')
 # Rebind only copied text consumers; native code and provenance snapshots stay exact.
 for folder in (dst,ops):
  for f in folder.glob('*'):
   if f.is_file() and not f.is_symlink() and f.suffix in ('.py','.sh','.md'):
    text=f.read_text();f.write_text(text.replace('packet124b','packet124c'))
 # Retained K2 replay is exact archive bytes; only its local archive paths change.
 f=ops/'inputs/k2-replay/manifest.json';f.write_text(f.read_text().replace('packet124b-orchestration','packet124c-orchestration'))
 # Fresh local generated evidence/seals must be rebuilt, never inherited as a pass.
 for folder in (dst/'selections',):shutil.rmtree(folder)
 for name in ('ready.json','cpu-tests.json','cpu-final.json'):(ops/name).unlink()
 print(json.dumps(dict(restored=restored,binaries=binaries)))
if __name__=='__main__':
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 copy_bundle()
