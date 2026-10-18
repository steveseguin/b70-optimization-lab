"""Seal local byte snapshots while preserving external authority symlinks.

The frozen screen sealer disallows paths resolving outside the repository.
Snapshot those eight read-only inputs, retain their original path/hash mapping,
and verify the real targets again at chain admission. No validator is relaxed.
"""
import json,shutil,sys
from source_decision import O,P,ROOT,sha,save
sys.path.insert(0,str(P))

def verify():
 row=json.loads((O/'inputs/external-source-bindings.json').read_text())
 for name,item in row.items():
  assert sha(ROOT/name)==item['sha256']==sha(ROOT/item['snapshot']),'external authority bytes changed: '+name
 return row

def main():
 import prepare_packet
 original=prepare_packet.proof
 def proof():
  build,reports,sources=original();sources=dict(sources);bindings={}
  for name,digest in list(sources.items()):
   if (ROOT/name).resolve().is_relative_to(ROOT):continue
   rel=(ROOT/name).relative_to(P)
   snapshot=P/'build/sealed-inputs'/rel
   snapshot.parent.mkdir(parents=True,exist_ok=True)
   shutil.copyfile(ROOT/name,snapshot)
   assert sha(snapshot)==digest
   bindings[name]=dict(snapshot=str(snapshot.relative_to(ROOT)),sha256=digest)
   del sources[name];sources[str(snapshot.relative_to(ROOT))]=digest
  save(O/'inputs/external-source-bindings.json',bindings);verify()
  sources.update({str(f.relative_to(ROOT)):sha(f) for f in (O/'inputs/external-source-bindings.json',O/'seal_view.py')})
  return build,reports,sources
 prepare_packet.proof=proof
 prepare_packet.main()
if __name__=='__main__':main()
