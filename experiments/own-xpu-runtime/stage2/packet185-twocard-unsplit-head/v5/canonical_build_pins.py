"""Retain qualified binaries; canonicalize immutable object aliases only."""
import json,resource
from p185_v5_build_engine import P,LOCAL,ROOT,sha,save

def main():
 receipt=P/'evidence/build.json';prior=json.loads(receipt.read_text())
 driver=P/'p185_v5_build_engine.py';before=driver.read_text();old='inherited[str(src.relative_to(ROOT))]=sha(target)';new='inherited[str(src.resolve().relative_to(ROOT))]=sha(target)'
 assert before.count(old)==1
 for n,h in prior['sources'].items():assert sha(ROOT/n)==h,n
 for n,h in prior['artifacts'].items():assert sha(ROOT/n)==h,n
 save(LOCAL/'lineage-inputs/build-before-canonical-pins.json',prior)
 (LOCAL/'lineage-inputs/build-driver-before-canonical-pins.py').write_text(before)
 driver.write_text(before.replace(old,new))
 sources={}
 for n,h in prior['sources'].items():
  path=ROOT/n
  if path.suffix=='.o':
   resolved=path.resolve();assert resolved.is_file() and sha(resolved)==h
   n=str(resolved.relative_to(ROOT))
  if path==driver:h=sha(driver)
  sources[n]=h
 prior['sources']=sources
 prior['canonical_pin_reseal']=dict(native_sources_unchanged=True,binaries_unchanged=True,compiler_executed=False,reason='seal immutable resolved objects instead of inherited alias paths',original_receipt=str((LOCAL/'lineage-inputs/build-before-canonical-pins.json').relative_to(ROOT)),original_receipt_sha256=sha(LOCAL/'lineage-inputs/build-before-canonical-pins.json'))
 save(receipt,prior)
 print('Canonical immutable build pins PASS; native bytes unchanged')
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
