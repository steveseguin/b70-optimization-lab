import json,subprocess,hashlib,os
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build/parallel';OLD=P.parent/'packet29-merged'
assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
incs=['-I'+str(x.resolve()) for x in (P,OLD,OLD/'../../stage1/packet3-prep/src',OLD/'../packet2/kernels',OLD/'../packet2/loader')];rows=[]
for tag,cc in [('gcc','/usr/bin/g++'),('clang','/opt/intel/oneapi/compiler/2026.0/bin/compiler/clang++')]:
 cmd=[cc,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY',*incs,str(P/'parallel_cpu.cpp'),'-o',str(B/('cpu-'+tag))];r=subprocess.run(cmd,capture_output=True,text=True);(B/('cpu-'+tag+'.log')).write_text(r.stdout+r.stderr);rows.append(dict(tag=tag,command=cmd,returncode=r.returncode));print(tag,r.returncode,flush=True)
 if r.returncode:raise RuntimeError(r.stderr)
 for repeat in range(2):
  r=subprocess.run([str(B/('cpu-'+tag)),str(OLD/'build/fusion-fixtures')],capture_output=True,text=True);receipt=json.loads(r.stdout);rows.append(dict(tag=tag,repeat=repeat,returncode=r.returncode,binary_sha256=hashlib.sha256((B/('cpu-'+tag)).read_bytes()).hexdigest(),receipt=receipt));print('gate',repeat,r.returncode,flush=True)
  if r.returncode:raise RuntimeError(r.stderr+str(receipt))
(P/'parallel-gates.json').write_text(json.dumps(rows,indent=2)+'\n')
