"""Serial dual-compiler mock scheduling tests; no model or GPU execution."""
import json,os,subprocess
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits
def main():
 limits();runs=[];sources={}
 owner=P.parents[1]/'stage1/packet3-prep/src'
 for compiler,name in (('/usr/bin/g++','gnu'),('/opt/intel/oneapi/compiler/2026.0/bin/icpx','intel')):
  dest=B/('cpu-'+name);dest.mkdir(exist_ok=True)
  cmd=[compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-I'+str(P),'-I'+str(owner),str(P/'retirement_test.cpp'),str(P/'owner.cpp'),str(P/'owner_retire.cpp'),'-o',str(dest/'retirement-test')]
  with (dest/'compile.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,check=True,timeout=300)
  for repeat in (1,2):
   out=dest/f'repeat-{repeat}';out.mkdir(exist_ok=True)
   r=subprocess.run([str(dest/'retirement-test'),str(out)],stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True,timeout=60)
   (out/'run.log').write_text(r.stdout+r.stderr);native=json.loads(r.stdout)
   assert native['passed'] and native['negative_cases']==6 and native['ordered_queries']==4
   assert sha(out/'expected.bin')==sha(out/'candidate.bin')
   runs.append(dict(compiler=name,repeat=repeat,native=native,command=cmd,path=str(out.relative_to(ROOT)),expected_sha256=sha(out/'expected.bin'),candidate_sha256=sha(out/'candidate.bin')))
  print(name,'mock retirement PASS',flush=True)
 assert len({r['candidate_sha256'] for r in runs})==1
 for n in ('cpu_gate.py','retirement_test.cpp','owner.cpp','owner.hpp','owner_api.hpp','owner_retire.cpp','ordered_queue.hpp','argument_block.hpp'):
  sources[str((P/n).relative_to(ROOT))]=sha(P/n)
 save(P/'evidence/cpu-byte-identity.json',dict(passed=True,device_executed=False,cpu_model_executed=False,runs=runs,sources=sources))
if __name__=='__main__':main()
