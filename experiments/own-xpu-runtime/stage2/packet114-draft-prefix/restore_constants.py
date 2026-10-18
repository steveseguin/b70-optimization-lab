"""Restore ignored, hash-bound generated constants; never alter parent sources."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];BASE=P.parent/'packet103-record-bundle'
def main():
 pins=json.loads((P/'source-copy-provenance.json').read_text())['packet103']
 for name,digest in pins.items():
  source=ROOT/name
  if '/build/' not in str(source.relative_to(BASE/'build/checked')):continue
  raw=source.read_bytes();assert hashlib.sha256(raw).hexdigest()==digest
  dest=P/'sources'/source.relative_to(BASE/'build/checked');dest.parent.mkdir(parents=True,exist_ok=True)
  if dest.exists():assert dest.read_bytes()==raw
  else:dest.write_bytes(raw)
 dest=P/'sources'/BASE.relative_to(ROOT)/'rope.bf16';raw=(BASE/'rope.bf16').read_bytes()
 assert hashlib.sha256(raw).hexdigest()==json.loads((P/'constant-pins.json').read_text())['rope_sha256']
 if dest.exists():assert dest.read_bytes()==raw
 else:dest.write_bytes(raw)
if __name__=='__main__':main()
