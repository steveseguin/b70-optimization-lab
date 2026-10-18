"""Copy frozen packet133, preserve every link, omit only generated regular files."""
import hashlib,json,os,shutil,subprocess
from pathlib import Path
ROOT=Path('/home/steve/llm-optimizations');BASE=ROOT/'experiments/own-xpu-runtime'
O=BASE/'ops/packet133-orchestration';P=BASE/'stage2/packet133-record-bundle';OLD=P.with_name('packet133-record-bundle')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def links(p):
 out=subprocess.check_output(['find',str(p),'-type','l','-printf','%P\t%l\n'],stdin=subprocess.DEVNULL,text=True)
 return dict(line.split('\t',1) for line in out.splitlines())
def main():
 assert not P.exists();assert shutil.disk_usage('/').free>=25_000_000_000
 before=links(OLD)
 # Copy source and retained fixtures. Skip all regular generated build files,
 # chain/submission outputs and selections; link inventory is restored below.
 def ignore(path,names):
  rel=Path(path).relative_to(OLD)
  return [n for n in names if n=='__pycache__' or (rel==Path('.') and n in ('build','selections','submission'))]
 shutil.copytree(OLD,P,symlinks=True,ignore=ignore)
 for name,target in before.items():
  dest=P/name;dest.parent.mkdir(parents=True,exist_ok=True)
  if not dest.is_symlink():dest.symlink_to(target)
 assert links(P)==before
 # Read-only fixture reuse avoids copying historical scratch/builds.
 for name in ('cpu','reset-GNU','reset-Intel'):
  src=OLD/'build'/name;dest=P/'build'/name
  if src.is_dir():shutil.copytree(src,dest,symlinks=True)
  else:shutil.copy2(src,dest)
 src=BASE/'ops/packet133-orchestration'
 for f in src.iterdir():
  if f.name=='copy_bundle.py':continue
  d=O/f.name
  if f.is_symlink():d.symlink_to(os.readlink(f))
  elif f.is_dir():shutil.copytree(f,d,symlinks=True)
  else:shutil.copy2(f,d)
 for folder in (P,O):
  for f in folder.glob('*'):
   if f.is_file() and not f.is_symlink() and f.suffix in ('.py','.sh','.md'):
    f.write_text(f.read_text().replace('packet133','packet133'))
 f=O/'inputs/k2-replay/manifest.json';f.write_text(f.read_text().replace('packet133-orchestration','packet133-orchestration'))
 # No parent readiness/device output is inherited as current evidence.
 for name in ('ready.json','cpu-tests.json','cpu-final.json'):(O/name).unlink(missing_ok=True)
 (P/'selections').mkdir()
 audit=dict(passed=True,device_executed=False,parent=str(OLD.relative_to(ROOT)),restored=before,binaries={},find_type_l_parent=before,find_type_l_copy=links(P))
 (O/'inputs/symlink-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
 print('All',len(before),'parent symlinks preserved')
if __name__=='__main__':
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 main()
