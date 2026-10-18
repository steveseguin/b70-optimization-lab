"""Exact block decoding and signed PLE hash/rollback regression, GNU + Intel."""
import json,os,resource,subprocess
from pathlib import Path
from table_build import P,ROOT,admission,sha,save
from compile_turn import turn
def main():
 admission();b=P/'build/target';b.mkdir(parents=True,exist_ok=True);runs=[]
 for compiler,path in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  cmd=[path,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off',str(P/'target_cpu.cpp'),'-o',str(b/compiler)]
  with turn(),(b/(compiler+'-build.log')).open('w') as f:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=300)
  for repeat in (1,2):
   cp=subprocess.run([str(b/compiler)],stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True,timeout=120)
   row=json.loads(cp.stdout);assert row['passed'] and row['block_cases']==131072 and row['history_steps']==4096
   runs.append(dict(compiler=compiler,repeat=repeat,result=row,binary=str((b/compiler).relative_to(ROOT)),binary_sha256=sha(b/compiler)))
 sources={str(p.relative_to(ROOT)):sha(p) for p in (P/'target_gate.py',P/'target_cpu.cpp',P/'token_input.hpp',P.parent/'packet2/kernels/math.hpp')}
 save(P/'evidence/target.json',dict(passed=True,device_executed=False,runs=runs,sources=sources));print('GNU/Intel complete scale domains and signed PLE PASS',flush=True)
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
