"""Two CPU-only replay libraries, under the shared compiler turn."""
import json,resource,shlex,subprocess,sys
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits

def main():
 limits();sys.path.insert(0,str(P.parents[1]/'ops'));from compile_turn import turn
 rows=[];sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('router_cpu.cpp','cache_cpu.cpp','build_replay.py')}
 for name,cc in [('gnu','/usr/bin/g++'),('intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  binary=B/('router-'+name+'.so');commands=[];objects=[]
  flags=['-std=c++20','-O2','-march=native','-mfma','-ffp-contract=off','-fno-fast-math','-fopenmp','-DOWN_RT_HOST_ONLY',
   '-I'+str(P.parents[1]/'stage1/packet3-prep/src'),'-I'+str(P.parent/'packet2/kernels'),'-I'+str(P.parent/'packet2/loader'),'-fPIC']
  for stem in ('router_cpu','cache_cpu'):
   obj=B/f'{stem}-{name}.o';dep=B/f'{stem}-{name}.d'
   cmd=[cc,*flags,'-MMD','-MF',str(dep),'-c',str(P/(stem+'.cpp')),'-o',str(obj)];commands.append(cmd);objects.append(str(obj))
   with turn(),(B/f'{stem}-{name}.log').open('w') as log:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
   for name0 in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]):
    f=Path(name0).resolve()
    if f.is_relative_to(ROOT):sources[str(f.relative_to(ROOT))]=sha(f)
  cmd=[cc,'-shared','-fopenmp',*objects,'-o',str(binary)];commands.append(cmd)
  with turn(),(B/('router-'+name+'.log')).open('w') as log:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
  deps=subprocess.check_output(['readelf','-d',str(binary)],text=True,stdin=subprocess.DEVNULL)
  assert not any(x in deps.lower() for x in ('libsycl','ze_loader','opencl','libcuda'))
  rows.append(dict(compiler=name,path=str(binary.relative_to(ROOT)),sha256=sha(binary),commands=commands,dependencies=deps))
  print(name,'CPU replay build PASS',flush=True)
 save(P/'evidence/replay-build.json',dict(passed=True,device_executed=False,sources=sources,libraries=rows))
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
