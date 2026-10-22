"""One-time symlink-preserving source copy; no existing packet is modified."""
import hashlib,json,os,shutil,resource
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];O=Path(__file__).resolve().parent
P=ROOT/'experiments/own-xpu-runtime/stage2/packet187-record-bundle-v3'
OLD=P.with_name('packet136-record-bundle');STATIC=P.with_name('packet153-snapshot-host')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert not P.exists()
 assert shutil.disk_usage('/').free-100_000_000>=30_000_000_000
 def ignore(path,names):
  rel=Path(path).relative_to(OLD)
  return [n for n in names if n=='__pycache__' or (rel==Path('.') and n in ('build','selections','submission'))]
 shutil.copytree(OLD,P,symlinks=True,ignore=ignore)
 sources={};links={}
 for base,dirs,files in os.walk(P,followlinks=False):
  for name in dirs+files:
   f=Path(base)/name;rel=str(f.relative_to(P))
   if f.is_symlink():links[rel]=os.readlink(f)
   elif f.is_file():sources[rel]=sha(f)
 (O/'inputs').mkdir()
 (O/'inputs/packet136-copy.json').write_text(json.dumps(dict(parent=str(OLD.relative_to(ROOT)),files=sources,symlinks=links,excluded=['build','selections','submission','__pycache__']),indent=2)+'\n')
 # Historical metadata cannot be mistaken for new qualification.
 history=P/'lineage-inputs/packet136-history';history.mkdir(exist_ok=True)
 for f in list(P.glob('*.json')):
  if f.name not in ('oracle-binding.json','selection.json','selection-template.json','memory-plan.json','dispatch-speed6.json','dispatch-default.json','dispatch-p45.json','dispatch-speed6-provenance.json','placement-policy.json','input-fixtures.json'):
   shutil.move(f,history/f.name)
 vendor=P/'snapshot-static';vendor.mkdir()
 shutil.copytree(STATIC/'native-base',vendor/'native-base',symlinks=True)
 shutil.copytree(STATIC/'v5/native-src',vendor/'native-src',symlinks=True)
 for name in ('strict_snapshot.hpp','rank.hpp','main.cpp','native_controller.hpp','layout_bytes.cpp','snapshot-static.patch'):
  if (STATIC/name).is_file():shutil.copy2(STATIC/name,vendor/name)
 shutil.copytree(STATIC/'lineage-inputs',vendor/'lineage-inputs',symlinks=True,ignore=lambda p,n:[x for x in n if x not in ('capture-extents.csv',)] if Path(p)==STATIC/'lineage-inputs' else [])
 binaries={}
 for mode in ('gnu-host','device'):
  source=STATIC/'v5/build'/mode/'own-rt-iq3';dest=P/'build'/mode/source.name;dest.parent.mkdir(parents=True)
  shutil.copy2(source,dest);assert sha(source)==sha(dest)
  binaries[str(dest.relative_to(P))]=dict(sha256=sha(dest),origin=str(source.relative_to(ROOT)))
 frozen={str(f.relative_to(P)):sha(f) for f in vendor.rglob('*') if f.is_file() and not f.is_symlink()}
 (O/'inputs/packet153-native.json').write_text(json.dumps(dict(schema='packet187.native-binding.v1',binaries=binaries,sources=frozen),indent=2)+'\n')
 assert shutil.disk_usage('/').free>=30_000_000_000
 print(json.dumps(dict(copied_sources=len(sources),symlinks=len(links),vendored_sources=len(frozen),binary_bytes=sum((P/n).stat().st_size for n in binaries),free_bytes=shutil.disk_usage('/').free)))
if __name__=='__main__':main()
