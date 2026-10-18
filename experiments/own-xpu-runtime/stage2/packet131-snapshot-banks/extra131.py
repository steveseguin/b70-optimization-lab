"""Production recurrence and reset regressions under both compilers, CPU only."""
import json,subprocess
from build131 import P,ROOT,B,sha,save,cpu_main,limits,run
def main():
 commands=[];runs=[]
 for compiler,cxx in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  binary=B/('recurrence131-'+compiler)
  cmd=[cxx,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-I'+str(P),'-I'+str(P.parents[1]/'stage1/packet3-prep/src'),'-I'+str(P.parent/'packet2/kernels'),'-I'+str(P.parent/'packet2/loader'),str(P/'recurrence131.cpp'),'-o',str(binary),'-lcrypto']
  commands.append(run(cmd,'recurrence-'+compiler))
  for repeat in (1,2):
   cp=subprocess.run([str(binary)],stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True,timeout=180)
   runs.append(dict(compiler=compiler,repeat=repeat,binary_sha256=sha(binary),**json.loads(cp.stdout)))
  print(compiler,'production recurrence all six banks PASS',flush=True)
 sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'extra131.py',P/'recurrence131.cpp',P/'p82_cpu.cpp',P/'p82_recurrence.hpp',P/'p82b_recurrence.hpp']}
 save(P/'evidence/recurrence131.json',dict(passed=True,device_executed=False,runs=runs,commands=commands,sources=sources))
 import reset_regression
 reset_regression.main();limits()
if __name__=='__main__':cpu_main();main()
