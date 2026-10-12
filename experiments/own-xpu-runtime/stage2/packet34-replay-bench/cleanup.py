"""Archive required gate evidence, verify member bytes, delete only packet34 scratch."""
import hashlib,json,shutil,tarfile
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build'
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 assert json.loads((P/'cpu-tests.json').read_text())['passed']
 roots=[x for x in B.iterdir() if x.name.startswith(('gate-','pre-final-asan-','census','smoke','rejected-entry'))]
 keep=[];names={'receipt.json','iterations.jsonl','dynamic.jsonl','summary.json','failure.json','teardown.json','census.json','launch-plan.jsonl','allocations.json'}
 for root in roots:
  if root.is_file():keep.append(root)
  elif root.is_dir():keep.extend(x for x in root.rglob('*') if x.is_file() and x.name in names)
 keep.extend(x for x in B.iterdir() if x.is_file() and x.suffix=='.log' and x not in keep)
 assert keep
 evidence=P/'evidence';evidence.mkdir(exist_ok=True);archive=evidence/'cpu-preparation.tar.gz'
 inventory={str(x.relative_to(B)):sha(x) for x in keep}
 with tarfile.open(archive,'w:gz',compresslevel=6) as tar:
  for x in keep:tar.add(x,arcname=str(x.relative_to(B)),recursive=False)
 with tarfile.open(archive,'r:gz') as tar:
  assert set(tar.getnames())==set(inventory)
  for m in tar:
   f=tar.extractfile(m);assert f is not None
   h=hashlib.sha256()
   for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
   assert h.hexdigest()==inventory[m.name],m.name
 # Only generated diagnostic per-site CPU timing text is not retained. The
 # per-iteration comparisons, dynamic evidence, failure and final receipts are.
 for root in roots:
  assert root.parent==B
  if root.is_dir():shutil.rmtree(root)
  else:root.unlink()
 if (B/'tmp').exists():shutil.rmtree(B/'tmp')
 for x in keep:
  if x.exists() and x.parent==B and x.suffix=='.log':x.unlink()
 receipt={'passed':True,'archive':'evidence/cpu-preparation.tar.gz','sha256':sha(archive),'members_sha256':inventory,'scratch_deleted':True,'retained_ignored':'build/{host,icpx-host,asan,device}: binaries and rebuild objects','discarded':'redundant CPU sites/timings/progress text; regeneration by cpu_gates.py; no native execution evidence exists'}
 (P/'scratch-cleanup.json').write_text(json.dumps(receipt,indent=2)+'\n')
 (evidence/'RETENTION.md').write_text('CPU preparation receipts, complete per-iteration comparison logs, dynamic-data logs, source census and build logs. No device measurements. Every tar member was hashed before removal and checked after compression; see ../scratch-cleanup.json. Rebuild with build.py modes, then cpu_gates.py. Ignored coordinator binaries remain in build/. Redundant per-site CPU timing text was disposable generator output and is reproducible.\n')
 print(json.dumps({'members':len(inventory),'bytes':archive.stat().st_size,'scratch_deleted':True}))
if __name__=='__main__':main()
