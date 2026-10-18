"""Run the same capture header on GNU and Intel, twice, with byte evidence."""
import json,subprocess,sys,tempfile
from build_engine import P,ROOT,B,limits,sha,save
sys.path.insert(0,str(P.parents[1]/'ops'))
from compile_turn import turn
def main():
 limits();runs=[]
 for name,compiler in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  binary=B/('capture-cpu-'+name)
  cmd=[compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off',str(P/'capture_cpu.cpp'),'-lcrypto','-o',str(binary)]
  with turn(),(B/('capture-cpu-'+name+'.log')).open('w') as log:
   subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
  for repeat in (1,2):
   with tempfile.TemporaryDirectory(prefix='p138-cpu-',dir=B) as tmp:
    cp=subprocess.run([str(binary),tmp],stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True,timeout=30)
    result=json.loads(cp.stdout)
    result.update(compiler=name,repeat=repeat,binary_sha256=sha(binary),route_hashes=[sha(Path(tmp)/str(r)/'capture.bin') for r in (0,1)])
    runs.append(result)
 assert len({tuple(r['route_hashes']) for r in runs})==1
 save(P/'evidence/capture-cpu.json',dict(passed=True,device_executed=False,runs=runs,sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'capture_cpu.cpp',P/'route_capture.hpp',P/'cpu_gate.py',P.parent/'packet94-hc-norm-fusion/compile_turn.py')}))
 print('GNU/Intel x2 capture bytes/rollback/boundary tests PASS')
from pathlib import Path
if __name__=='__main__':
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 main()
