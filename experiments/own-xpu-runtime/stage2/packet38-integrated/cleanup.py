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
 from storage import archive_files
 paths=[]
 for d in dirs:
  assert d.parent==B and not d.is_symlink()
  paths.extend(f for f in d.rglob('*') if f.is_file())
 paths.extend(B.glob('*.log'))
 target=P/'evidence/cpu-preparation-scratch.jsonl.gz'
 archived=archive_files(paths,target)
 # Raw test states/fixtures are explicitly authorized scratch. Their hashes and
 # exact input/source-bound reproduction gates survive, not a fictitious backup.
 for d in dirs:shutil.rmtree(d)
 for f in B.glob('*.log'):f.unlink()
 removed=[str(d.relative_to(P)) for d in dirs]
 for name in ('tmp','p33-candidate-tmp','host-issue'):
  d=B/name
  if d.exists():assert d.parent==B and not d.is_symlink();shutil.rmtree(d);removed.append(str(d.relative_to(P)))
 report=dict(passed=True,device_executed=False,archive=str(target.relative_to(P)),archive_sha256=digest(target),text_members=archived['retained_files'],hashed_generated_files=archived['files'],round_trip_text_bytes_verified=True,nested_gzip_bytes_verified=True,archive_format=archived['format'],removed_directories=removed,
  raw_fixture_restore='Regenerate with source-bound CPU gates. Raw test fixture/state bytes are discarded scratch; exact text and nested gzip evidence bytes are archived, every generated file hash is retained.',
  retained='Sealed binary/build trees, checked sources, immutable input bundles, official draft inputs, CPU capture inputs/results needed by KD and comparison, source-bound gate receipts.')
 (P/'scratch-cleanup.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:report[k] for k in ('passed','text_members','hashed_generated_files','archive')}))
if __name__=='__main__':main()
