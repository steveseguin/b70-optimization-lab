"""Archive generated CPU test text and file hashes, then remove packet-local scratch."""
import base64,gzip,hashlib,json,shutil
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build'
def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
 return h.hexdigest()
def main():
 seal=json.loads((P/'build-receipt.json').read_text());assert seal['passed'] and seal['device_executed'] is False
 prefixes=('linked-fixtures-','first-mini','real-','gates-','validation-','fixtures-','entry-codes-','resident-host-','canary-host-','fault-gates-','review-','suite-gates-','suite-real-','window-cpu-','native-mini-')
 dirs=[d for d in B.iterdir() if d.is_dir() and d.name.startswith(prefixes)]
 records=[];index=[]
 for d in dirs:
  assert d.parent==B and not d.is_symlink()
  for f in sorted(d.rglob('*')):
   if not f.is_file():continue
   assert not f.is_symlink(),str(f)
   row=dict(path=str(f.relative_to(P)),bytes=f.stat().st_size,sha256=digest(f));index.append(row)
   if f.suffix in ('.json','.jsonl','.log','.txt','.tsv'):
    records.append(row|dict(base64=base64.b64encode(f.read_bytes()).decode()))
 for f in sorted(B.glob('*.log')):
  records.append(dict(path=str(f.relative_to(P)),bytes=f.stat().st_size,sha256=digest(f),base64=base64.b64encode(f.read_bytes()).decode()))
 payload=dict(text=records,file_index=index);raw=json.dumps(payload,separators=(',',':')).encode();blob=gzip.compress(raw,mtime=0)
 target=P/'evidence/cpu-preparation-scratch.json.gz';target.parent.mkdir(exist_ok=True);target.write_bytes(blob)
 restored=json.loads(gzip.decompress(target.read_bytes()));assert restored==payload
 for row in restored['text']:
  data=base64.b64decode(row['base64']);assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
 # Raw test states/fixtures are explicitly authorized scratch. Their hashes and
 # exact input/source-bound reproduction gates survive, not a fictitious backup.
 for d in dirs:shutil.rmtree(d)
 for f in B.glob('*.log'):f.unlink()
 removed=[str(d.relative_to(P)) for d in dirs]
 for name in ('tmp','p33-candidate-tmp','host-issue'):
  d=B/name
  if d.exists():assert d.parent==B and not d.is_symlink();shutil.rmtree(d);removed.append(str(d.relative_to(P)))
 report=dict(passed=True,device_executed=False,archive=str(target.relative_to(P)),archive_sha256=digest(target),text_members=len(records),hashed_generated_files=len(index),round_trip_text_bytes_verified=True,removed_directories=removed,
  raw_fixture_restore='Regenerate with source-bound CPU gates. Raw test fixture/state bytes are discarded scratch; only text is archived, every generated file hash is retained.',
  retained='Sealed binary/build trees, checked sources, immutable input bundles, official draft inputs, CPU capture inputs/results needed by KD and comparison, source-bound gate receipts.')
 (P/'scratch-cleanup.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:report[k] for k in ('passed','text_members','hashed_generated_files','archive')}))
if __name__=='__main__':main()
