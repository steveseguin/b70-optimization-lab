"""Actual controller + interleave state, forced arrivals, GNU/Intel fresh runs."""
import json,resource,subprocess
from build_engine import P,B,ROOT,sha,save,limits
from compile_turn import turn
def main():
 limits();out=B/'controller';out.mkdir(exist_ok=True);runs=[];commands=[]
 for compiler,cxx in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  binary=out/compiler
  cmd=[cxx,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-pthread',str(P/'p130_controller_test.cpp'),'-o',str(binary)]
  with turn(),(out/(compiler+'.log')).open('w') as log:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
  commands.append(cmd)
  for repeat in (1,2):
   r=subprocess.run([str(binary)],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
   assert r.returncode==0,r.stderr
   row=json.loads(r.stdout);assert row['passed'] and row['cases']==40 and row['negative_controls']==7
   runs.append(dict(compiler=compiler,repeat=repeat,binary=str(binary.relative_to(ROOT)),binary_sha256=sha(binary),**row))
  negative=subprocess.run([str(binary),'--old-deferred-negative'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
  assert negative.returncode!=0 and 'early service did not occur' in negative.stderr,negative.stderr
  print(compiler,'early/late, hits/misses, EOS, stale/abort/reset PASS',flush=True)
 save(P/'evidence/controller.json',dict(passed=True,device_executed=False,runs=runs,commands=commands,sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'controller_gate.py',P/'p130_controller_test.cpp',P/'p130_interleave.hpp',P/'native_controller.hpp',P/'p105_common.hpp']}))
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));main()
