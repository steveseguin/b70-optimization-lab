"""Exercise real layout guards with the full-size CPU-only startup fixture."""
import json,subprocess,shutil
from build_engine import P,ROOT,B,sha,save,limits
def main():
 limits();binary=B/'full-shape/fixture';runs=[]
 cases={'serial':'requires','gemv':'requires','streaming':'requires','draft-rank':'requires','split':'requires','context':'requires','legacy':'requires','short':'extent','misaligned':'extent'}
 for choice in ('head-split-compute','head-split-bcs'):
  selection=P/'selections'/choice/'selection.json'
  for case,reason in cases.items():
   dest=B/'refusal-scratch';cmd=[str(binary),str(selection),sha(selection),'1',str(dest),case,'1','0']
   r=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
   assert r.returncode and reason in r.stderr,(choice,case,r.returncode,r.stderr)
   runs.append(dict(choice=choice,case=case,returncode=r.returncode,error=r.stderr,command=cmd));shutil.rmtree(dest)
 sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'startup_refusals.py',P/'main.cpp',P/'p105_runtime.hpp',binary)}
 save(P/'evidence/startup-refusals.json',dict(passed=True,device_executed=False,runs=runs,sources=sources));print('18 real startup/layout refusals PASS')
if __name__=='__main__':main()
