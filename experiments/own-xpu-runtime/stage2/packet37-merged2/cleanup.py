"""Archive bounded preparation receipts/logs, verify bytes, delete only packet scratch."""
import base64,gzip,hashlib,json,shutil
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build'
def sha(data):return hashlib.sha256(data).hexdigest()
def main():
 build=json.loads((P/'build-receipt.json').read_text());assert build['passed']
 prefixes=('linked-fixtures-','first-mini','real-','gates-','validation-','fixtures-','entry-codes-','resident-host-','canary-host-','fault-gates-','review-')
 dirs=[d for d in B.iterdir() if d.is_dir() and d.name.startswith(prefixes)]
 files=[]
 for d in dirs:
  if d.name.startswith('real-'):
   files += [f for f in d.rglob('*') if f.is_file() and f.suffix in ('.json','.log','.txt')]
  else:
   files += [f for f in d.rglob('*') if f.is_file() and f.name in ('receipt.json','ownership.json','failure-before-teardown.json') and not any(x.startswith(('case-','state-')) for x in f.relative_to(d).parts)]
 files += [f for f in B.iterdir() if f.is_file() and f.suffix=='.log']
 if not dirs and not files:
  print('no new scratch; retained previous archive and cleanup receipt');return
 records=[]
 for f in sorted(set(files)):
  data=f.read_bytes();records.append(dict(path=str(f.relative_to(P)),bytes=len(data),sha256=sha(data),base64=base64.b64encode(data).decode()))
 raw=json.dumps(records,separators=(',',':')).encode();packed=gzip.compress(raw,mtime=0)
 target=P/('evidence/preparation-logs-p37-'+sha(raw)[:16]+'.json.gz');target.parent.mkdir(exist_ok=True)
 if target.exists():assert target.read_bytes()==packed
 else:target.write_bytes(packed)
 restored=json.loads(gzip.decompress(target.read_bytes()));assert len(restored)==len(records)
 for row in restored:
  data=base64.b64decode(row['base64']);assert len(data)==row['bytes'] and sha(data)==row['sha256']
 removed=[]
 for d in dirs:
  assert d.parent==B and not d.is_symlink();removed.append(str(d.relative_to(P)));shutil.rmtree(d)
 for f in B.iterdir():
  if f.is_file() and (f.suffix=='.log' or f.name.startswith('real-') and f.suffix=='.txt'):f.unlink()
 for name in ('tmp','host','p33-candidate-tmp','host-issue'):
  d=B/name
  if d.exists():shutil.rmtree(d);removed.append(str(d.relative_to(P)))
 for name in ('expert-down-review-gcc','expert-down-review-icpx'):
  f=B/name
  if f.exists():f.unlink()
 report=dict(passed=True,device_executed=False,archive=str(target.relative_to(P)),archive_sha256=sha(packed),
  uncompressed_sha256=sha(raw),entries=len(records),round_trip_bytes_verified=True,removed_directories=removed,
  retained='final gnu-host/icpx-host/asan/device binaries, rebuild trees, checked mirror, input, fixtures and generated headers for coordinator',
  restore='python -B cleanup.py creates the gzip JSON archive. Decode each base64 member and verify its SHA-256 before writing. Raw mini states regenerate through gates.py; retained real fixture bytes equal the v2 oracle, with hashes in real-*.json.',
  evidence_policy='Test-generated scratch only. Final consolidated gates and failure evidence remain tracked; no other packet touched.')
 (P/'scratch-cleanup.json').write_text(json.dumps(report,indent=2)+'\n')
 print('archived',len(records),'text receipts; removed',len(removed),'scratch directories')
if __name__=='__main__':main()
