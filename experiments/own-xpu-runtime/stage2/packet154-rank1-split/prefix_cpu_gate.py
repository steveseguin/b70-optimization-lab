"""Exact head prefix rows, tie order, suffix poison and controller CPU checks."""
import json,subprocess,shlex,time
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits
from compile_turn import turn as compiler_turn
CHECKED=P

def main():
 limits();out=B/'cpu';out.mkdir(exist_ok=True);runs=[];sources={};commands=[];binaries={}
 for label,cxx in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  binary=out/('prefix-'+label);dep=out/('prefix-'+label+'.d')
  cmd=[cxx,'-std=c++20','-O2','-g0','-fno-fast-math','-ffp-contract=off','-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-fopenmp','-pthread','-DOWN_RT_HOST_ONLY','-DNDEBUG','-I'+str(CHECKED),'-I'+str(P),'-I'+str(P.parents[1]/'stage1/packet3-prep/src'),'-I'+str(P.parent/'packet2/kernels'),'-I'+str(P.parent/'packet2/loader'),'-MMD','-MF',str(dep),str(P/'prefix_cpu.cpp'),'-o',str(binary)]
  if label=='Intel':cmd.insert(1,'-Wl,-rpath,/opt/intel/oneapi/compiler/2026.0/lib')
  commands.append(cmd)
  with compiler_turn(),(out/(label+'-compile.log')).open('w') as log:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True)
  for n in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]):sources[str(Path(n).resolve().relative_to(ROOT))]=sha(n)
  for n in (91392,80128):
   for repeat in (0,1):
    start=time.monotonic();r=subprocess.run([str(binary),str(n)],stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
    row=json.loads(r.stdout);assert row['passed'] and row['sealed_n']==n
    path=P/'evidence'/f'prefix-{label}-{n}-{repeat}.json';save(path,row)
    runs.append(dict(compiler=label,rows=n,repeat=repeat,result=row,seconds=time.monotonic()-start))
   assert runs[-1]['result']==runs[-2]['result']
  binaries[str(binary.relative_to(ROOT))]=sha(binary)
  print(label,'both prefixes, two fresh exact-byte/controller runs PASS',flush=True)
 for f in (P/'prefix_cpu_gate.py',P/'prefix_cpu.cpp'):sources[str(f.relative_to(ROOT))]=sha(f)
 save(P/'evidence/prefix-byte-identity.json',dict(passed=True,device_executed=False,runs=runs,sources=sources,binaries=binaries,commands=commands,scope='Synthetic complete 248320x2560 Q6 head compared bytewise with each prefix, untouched poisoned suffix, actual round2 lower-ID ties, native target verification/rollback; not full-model device quality.'))
if __name__=='__main__':main()
