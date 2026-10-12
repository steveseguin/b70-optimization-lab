"""Retain compact completed-test receipts before removing regenerated scratch."""
import base64,gzip,hashlib,json,shutil
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build'
def sha(data):return hashlib.sha256(data).hexdigest()
def main(partial=False):
 if not partial:
  assert json.loads((P/'build-receipt.json').read_text())['passed']
 prefixes=('first-mini','mini-mtp-first','gates-','mtp-gates-','validation-','fixtures-','entry-codes-','resident-host-','canary-host-','fault-gates-','review-')
 if not partial:prefixes+=('real-',)
 dirs=[d for d in B.iterdir() if d.is_dir() and d.name.startswith(prefixes)]
 duplicate_restores=[]
 if not partial:
  for receipt in P.glob('capture-repeat-*.json'):
   name=receipt.name.removeprefix('capture-repeat-').removesuffix('.json')
   repeat=json.loads(receipt.read_text());run=json.loads((P/f'capture-run-{name}.json').read_text())
   old=Path(run['previous']['output']);current=Path(run['output'])
   if not old.exists():continue
   assert repeat['passed'] and old.parent==B and current.parent==B and old!=current
   actual={str(f.relative_to(old)) for f in old.rglob('*') if f.is_file() and f.suffix in ('.bf16','.bin')}
   assert actual==set(repeat['sha256'])
   for relative,digest in repeat['sha256'].items():
    assert sha((old/relative).read_bytes())==digest==sha((current/relative).read_bytes())
   duplicate_restores.append(dict(removed=str(old.relative_to(P)),restore_from=str(current.relative_to(P)),
                                  fixture_sha256=repeat['sha256'],repeat_receipt=receipt.name))
   dirs.append(old)
 records=[]
 for d in dirs:
  for f in sorted(d.rglob('*')):
   if not f.is_file() or f.suffix not in ('.json','.jsonl','.log','.txt'):continue
   data=f.read_bytes()
   records.append(dict(path=str(f.relative_to(P)),bytes=len(data),sha256=sha(data),base64=base64.b64encode(data).decode()))
 if not dirs:return
 raw=json.dumps(records,separators=(',',':')).encode();packed=gzip.compress(raw,mtime=0)
 target=P/('evidence/preparation-logs-p36-'+sha(raw)[:16]+'.json.gz');target.parent.mkdir(exist_ok=True)
 if target.exists():assert target.read_bytes()==packed
 else:target.write_bytes(packed)
 restored=json.loads(gzip.decompress(target.read_bytes()));assert len(restored)==len(records)
 for row in restored:
  data=base64.b64decode(row['base64']);assert len(data)==row['bytes'] and sha(data)==row['sha256']
 # Point historical capture records at their byte-verified restoration sources
 # before removing duplicated fixture files.
 for mapping in duplicate_restores:
  name=Path(mapping['repeat_receipt']).name.removeprefix('capture-repeat-').removesuffix('.json')
  path=P/f'capture-run-{name}.json';run=json.loads(path.read_text())
  run['previous']['restoration']=dict(fixtures=mapping['restore_from'],fixture_hashes=mapping['repeat_receipt'],
                                    original_text_archive=str(target.relative_to(P)))
  path.write_text(json.dumps(run,indent=2)+'\n')
 removed=[];reclaimed=0
 for d in dirs:
  assert d.parent==B and not d.is_symlink()
  reclaimed+=sum(f.stat().st_size for f in d.rglob('*') if f.is_file())
  removed.append(str(d.relative_to(P)));shutil.rmtree(d)
 if not partial:
  for name in ('tmp','host'):
   d=B/name
   if d.exists():shutil.rmtree(d);removed.append(str(d.relative_to(P)))
 result=dict(passed=True,device_executed=False,partial=partial,duplicate_fixture_restore=duplicate_restores,archive=str(target.relative_to(P)),archive_sha256=sha(packed),
   uncompressed_sha256=sha(raw),entries=len(records),round_trip_bytes_verified=True,removed_directories=removed,reclaimed_logical_bytes=reclaimed,
   retained='final binaries/build trees, captured inputs and draft fixture bytes, consolidated gates and archives',
   regeneration='Rebuild scratch through build.py cheap/real. Captured target layer bytes equal the retained v2 oracle; hashes and match counts remain in real-*.json.',
   restore='Decode base64 members from gzip JSON and verify SHA256 before restoring beneath this packet only.',
   evidence_policy='Only completed generated test scratch; no source model, another packet, active real run, or KD fixture touched.')
 receipt=P/('scratch-cleanup-'+sha(raw)[:16]+'.json');receipt.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:result[k] for k in ('entries','reclaimed_logical_bytes','archive')}))
if __name__=='__main__':
 import sys
 main('--completed-cheap-only' in sys.argv)
