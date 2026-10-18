"""Restore byte-verified micro evidence; never replace an existing file."""
import gzip,hashlib,json
from build_engine import P,sha

def restore():
 row=json.loads((P/'evidence/micro-retention104b.json').read_text())
 for item in row['files']:
  source=P/item['compressed'];target=P/item['original']
  assert sha(source)==item['compressed_sha256']
  if target.exists():assert sha(target)==item['sha256'];continue
  data=gzip.decompress(source.read_bytes());assert len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256']
  with target.open('xb') as f:f.write(data)
if __name__=='__main__':restore()
