"""Re-admit previously compiled packet142 bytes against their complete native closure.
No compiler bypass: this executes neither compiler nor device. The only differing
recorded input is the Python build driver (artifact-path bookkeeping); every
recorded native source and inherited object must match, as must both binaries.
"""
import json,resource
from pathlib import Path
from p142_v5_build_engine import P,LOCAL,ROOT,sha,save,limits

def main():
 limits();prior=LOCAL/'lineage-inputs/qualified-v5/build.json';row=json.loads(prior.read_text())
 assert row['passed'] and not row['device_executed']
 driver=str((P/'build_engine.py').relative_to(ROOT));sources={k:v for k,v in row['sources'].items() if k!=driver}
 assert driver in row['sources']
 for name,digest in sources.items():assert sha(ROOT/name)==digest,'qualified native input changed: '+name
 # Pin immutable object targets, not mutable chains of ancestor aliases.
 sources={str((ROOT/name).resolve().relative_to(ROOT)) if name.endswith('.o') else name:digest for name,digest in sources.items()}
 artifacts={str((P/name).relative_to(ROOT)):digest for name,digest in row['artifacts'].items()}
 for name,digest in artifacts.items():assert sha(ROOT/name)==digest,'qualified binary changed: '+name
 # The full-shape and byte receipts remain byte-identical, not rewritten as new runs.
 for name in ('full-shape','bytes'):
  original=LOCAL/'lineage-inputs/qualified-v5'/(name+'.json');current=P/'evidence'/(name+'.json');assert sha(original)==sha(current)
  proof=json.loads(current.read_text())
  for source,digest in proof['sources'].items():assert sha(ROOT/source)==digest,'qualified CPU input changed: '+source
  if name=='full-shape':assert sha(P/'build/full-shape/fixture')==proof['binary_sha256']
  else:
   for source,digest in proof['binaries'].items():assert sha(ROOT/source)==digest
  sources[str(original.relative_to(ROOT))]=sha(original)
 sources.update({str(f.relative_to(ROOT)):sha(f) for f in (prior,P/'reuse_qualified.py',P/'p142_v5_build_engine.py',LOCAL/'kernel_guard.hpp')})
 save(P/'evidence/build.json',dict(schema='packet142.qualified-native-reuse.v1',passed=True,device_executed=False,compiler_executed=False,reused_same_packet_binaries=True,native_source_differences=0,original_build_receipt=str(prior.relative_to(ROOT)),original_build_receipt_sha256=sha(prior),original_build_driver_sha256=row['sources'][driver],build_driver_change='artifact paths and source-map bookkeeping only; existing compiler commands retained',sources=sources,artifacts=artifacts,commands=row['commands'],max_rss_kib=row['max_rss_kib'],build_bytes=limits()))
 print('Qualified packet142 native inputs and both binary hashes match; CPU receipts retained exactly')
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
