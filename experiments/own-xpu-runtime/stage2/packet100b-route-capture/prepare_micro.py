"""Reuse packet100's unchanged native micro binary, with new capture bindings."""
import json,os
from build_engine import P,ROOT,sha,save,limits
BASE=P.parent/'packet100-down-locality'

def main():
 limits()
 origin=json.loads((BASE/'evidence/microbench-build.json').read_text())
 assert origin['passed'] and not origin['device_executed']
 for name,digest in origin['sources'].items():assert sha(ROOT/name)==digest,name
 assert sha(BASE/'build/microbench')==origin['artifacts']['build/microbench']
 save(P/'micro-origin.snapshot.json',origin)
 dest=P/'build/microbench'
 if not dest.exists():os.link(BASE/'build/microbench',dest)
 assert sha(dest)==sha(BASE/'build/microbench')
 # Pin compilation inputs, not an ancestor's build/orchestration receipts.
 sources={n:h for n,h in origin['sources'].items() if Path(n).suffix in ('.cpp','.hpp','.h','.inc')}
 for path in (P/'micro-origin.snapshot.json',P/'prepare_micro.py',P/'run_micro.py',P/'qualification.py',P/'capture_inputs.py',P/'shared-wrapper-pin.json',BASE/'micro_gate.py'):
  sources[str(path.relative_to(ROOT))]=sha(path)
 save(P/'evidence/microbench-build.json',dict(passed=True,device_executed=False,
  reuse='exact unchanged packet100 micro binary and compiled kernel dependencies',sources=sources,
  artifacts={'build/microbench':sha(dest)},binary_sha256=sha(dest)))
 print('unchanged packet100 micro identity PASS; no compile/device run')
from pathlib import Path
if __name__=='__main__':main()
