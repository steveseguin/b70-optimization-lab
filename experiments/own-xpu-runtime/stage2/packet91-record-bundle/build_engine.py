"""Reuse immutable parent binaries by hash. This packet performs no compilation."""
import hashlib,json,os,resource,shutil
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];B=P/'build'
PARENTS={'rec-parallel':P.parent/'packet84-record-bundle','rec-both-plus':P.parent/'packet82b-recurrence2'}
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 assert shutil.disk_usage(ROOT).free>=12_000_000_000,'root free below 12 GB: stop'
def provenance():
 from chain_seal import check_map
 row=json.loads((P/'build-provenance.json').read_text())
 assert row['passed'] and not row['device_executed'];check_map(ROOT,row['sources'])
 for variant in row['variants'].values():
  for value in variant['binaries'].values():assert sha(ROOT/value['path'])==value['sha256']
 return row
def activate(recurrence):
 row=provenance();variant=row['variants'][recurrence];artifacts={}
 for mode,item in variant['binaries'].items():
  dst=B/mode/'own-rt-iq3';dst.parent.mkdir(parents=True,exist_ok=True)
  if dst.is_symlink():dst.unlink()
  assert not dst.exists(),'refuse replacing a non-symlink binary'
  dst.symlink_to(ROOT/item['path']);artifacts[str(dst.relative_to(P))]=item['sha256']
 save(P/'build-device-receipt.json',dict(schema='packet91.reused-build.v1',passed=True,device_executed=False,
      recurrence=recurrence,sources=row['sources'],artifacts=artifacts,provenance_sha256=sha(P/'build-provenance.json')))
def main():
 limits();sources={};variants={}
 from chain_seal import check_map
 baseline=PARENTS['rec-parallel']
 for f in baseline.iterdir():
  if f.is_file() and f.suffix in ('.cpp','.hpp','.inc','.bf16','.tsv'):
   assert sha(P/f.name)==sha(f),f.name
 for rec,parent in PARENTS.items():
  path=parent/'build-device-receipt.json';r=json.loads(path.read_text())
  assert r['passed'] and r['device_executed'] is False
  check_map(ROOT,r['sources']);check_map(parent,r['artifacts'])
  sources.update(r['sources']);sources[str(path.relative_to(ROOT))]=sha(path)
  binaries={mode:dict(path=str((parent/leaf).relative_to(ROOT)),sha256=r['artifacts'][leaf])
            for mode,leaf in ((m,'build/'+m+'/own-rt-iq3') for m in ('device','gnu-host'))}
  variants[rec]=dict(parent=str(parent.relative_to(ROOT)),binaries=binaries)
 for f in [P/'build_engine.py',P/'parent-source-manifest.json',*P.glob('*.cpp'),*P.glob('*.hpp'),*P.glob('*.bf16'),*P.glob('*.tsv'),*(P/'variants').rglob('*')]:
  if f.is_file():sources[str(f.relative_to(ROOT))]=sha(f)
 save(P/'build-provenance.json',dict(schema='packet91.binary-reuse.v1',passed=True,device_executed=False,
      compiled=False,variants=variants,sources=sources))
 activate('rec-parallel');print('Both original binaries verified and pinned; no compilation')
if __name__=='__main__':main()
