"""Restore only missing generated source/receipt files after complete hash checks."""
import hashlib,json,tarfile
from pathlib import Path
from build_engine import P,B,ROOT,sha,limits
def main():
 limits();receipt=json.loads((P/'evidence/build-retention.json').read_text());archive=ROOT/receipt['archive']
 assert sha(archive)==receipt['sha256']
 with tarfile.open(archive,'r:gz') as tar:
  assert set(tar.getnames())==set(receipt['members'])
  for member in tar:
   assert member.isfile() and not Path(member.name).is_absolute() and '..' not in Path(member.name).parts
   data=tar.extractfile(member).read();expected=receipt['members'][member.name]
   assert len(data)==expected['bytes'] and hashlib.sha256(data).hexdigest()==expected['sha256']
  for member in tar:
   dest=B/member.name;data=tar.extractfile(member).read()
   assert dest.resolve().is_relative_to(B.resolve())
   if dest.exists():assert dest.read_bytes()==data
   else:dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
 print('Verified generated source and CPU receipts; no parent or binary changes')
if __name__=='__main__':main()
