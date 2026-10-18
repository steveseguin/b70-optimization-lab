"""Actual native scheduling with a split-head mock backend; both compilers."""
import subprocess,json,shlex
from build_engine import P,ROOT,B,sha,save,limits
from pathlib import Path
from compile_turn import turn
def main():
 limits();dest=B/'controller';dest.mkdir(exist_ok=True);runs=[];sources={};commands=[]
 for compiler,cxx in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  binary=dest/compiler;dep=dest/(compiler+'.d');cmd=[cxx,'-std=c++20','-O2','-pthread','-MMD','-MF',str(dep),str(P/'p105_controller_test.cpp'),'-o',str(binary)]
  with turn(),(dest/(compiler+'.log')).open('w') as log:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
  commands.append(cmd)
  for n in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]):sources[str(Path(n).resolve().relative_to(ROOT))]=sha(n)
  r=subprocess.run([str(binary)],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30);assert r.returncode==0,r.stderr
  runs.append(dict(compiler=compiler,binary_sha256=sha(binary),**json.loads(r.stdout)))
 sources[str((P/'controller_gate.py').relative_to(ROOT))]=sha(P/'controller_gate.py')
 save(P/'evidence/controller.json',dict(passed=True,device_executed=False,runs=runs,sources=sources,commands=commands));print('Both compilers: native hit/miss/no-guess/EOS head protocol PASS',flush=True)
if __name__=='__main__':main()
