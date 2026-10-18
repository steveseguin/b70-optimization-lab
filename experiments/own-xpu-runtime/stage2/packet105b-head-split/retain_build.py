"""Retain generated source and small raw CPU receipts, verifying every byte.

No originals are removed. Binaries/objects remain local rebuild artifacts.
"""
import gzip,hashlib,io,json,tarfile
from build_engine import P,ROOT,B,sha,save,limits
def main():
 limits();wanted=set()
 for report in [P/'build-device-receipt.json',P/'startup97e.json',*(P/'evidence').glob('*.json')]:
  try:r=json.loads(report.read_text())
  except (ValueError,UnicodeError):continue
  for n in r.get('sources',{}):
   path=ROOT/n
   if path.is_relative_to(B) and path.is_file() and path.suffix in ('.cpp','.hpp','.inc','.py','.json','.log','.d','.tsv'):wanted.add(path)
 for folder in ('cpu','controller','runtime-mock','full-shape','startup97e'):
  for f in (B/folder).rglob('*'):
   if f.is_file() and not f.is_symlink() and f.suffix in ('.json','.jsonl','.log','.cpp','.hpp','.d','.bf16','.bin','.f32','.u32'):wanted.add(f)
 members={str(f.relative_to(B)):dict(sha256=sha(f),bytes=f.stat().st_size) for f in sorted(wanted)}
 path=P/'evidence/generated-cpu-evidence.tar.gz'
 with path.open('wb') as stream,gzip.GzipFile(fileobj=stream,mode='wb',mtime=0) as gz,tarfile.open(fileobj=gz,mode='w') as tar:
  for f in sorted(wanted):
   data=f.read_bytes();info=tarfile.TarInfo(str(f.relative_to(B)));info.size=len(data);info.mode=0o644;tar.addfile(info,io.BytesIO(data))
 with tarfile.open(path,'r:gz') as tar:
  assert set(tar.getnames())==set(members)
  for item in tar:
   data=tar.extractfile(item).read();expected=members[item.name]
   assert len(data)==expected['bytes'] and hashlib.sha256(data).hexdigest()==expected['sha256']
 save(P/'evidence/build-retention.json',dict(passed=True,archive=str(path.relative_to(ROOT)),sha256=sha(path),members=members,reason='Generated source identities and fresh CPU byte/state/log evidence; restore_links.py validates members and restores missing local files; originals retained'))
 print(len(members),'generated/raw evidence files roundtrip verified;',path.stat().st_size,'compressed bytes')
if __name__=='__main__':main()
