#!/usr/bin/env python3
"""Root-operated bounded compile/proof; no Device/model/service code invoked."""
from pathlib import Path
import argparse,hashlib,json,os,resource,shutil,subprocess,time,importlib.util,re
P=Path(__file__).resolve().parent;R=P.parents[3]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def closure():
 files=set();todo=[P/'test_storage.cpp',P/'recurrent_policy.hpp']
 while todo:
  p=todo.pop().resolve()
  if p in files:continue
  files.add(p)
  for inc in re.findall(r'^\s*#\s*include\s*"([^"]+)"',p.read_text(),re.M):todo.append((p.parent/inc).resolve())
 return {str(p):sha(p) for p in sorted(files)}
def plan(d):
 compiler='/usr/bin/g++';flags=[compiler,'-std=c++20','-O2','-g0','-DOWN_RT_HOST_ONLY','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror=return-type']
 return [flags+['-MMD','-MF',str(d/'proof.d'),str(P/'test_storage.cpp'),'-o',str(d/'proof')],[str(d/'proof')]]
if __name__=='__main__':
 ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--plan',action='store_true');g.add_argument('--build',action='store_true');a=ap.parse_args()
 pins=closure();pins.update({str(P/n):sha(P/n) for n in ['build_cpu.py','prepare.py','precision.patch','evidence/source-checkpoint.json']})
 if a.plan:print(json.dumps({'commands':plan(P/'build/cpu-preview'),'source_sha256':pins,'no_device':True},indent=2));raise SystemExit
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32))
 assert all(os.environ.get(x)=='2' for x in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'))
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
 assert shutil.disk_usage(R).free>=27000000000+64*1024**2
 d=P/'build'/('cpu-'+str(time.time_ns()));d.mkdir(parents=True);commands=plan(d);receipt={'passed':False,'commands':commands,'source_sha256':pins,'compiler_sha256':sha(commands[0][0]),'scope':'actual changed HostTeam and graph; no Device/model/production controller qualification'}
 coordinator=R/'experiments/own-xpu-runtime/ops/compile_turn.py';spec=importlib.util.spec_from_file_location('recurrent_compile_turn',coordinator);turn=importlib.util.module_from_spec(spec);spec.loader.exec_module(turn)
 try:
  for i,cmd in enumerate(commands):
   with (d/('compile.log' if i==0 else 'proof.log')).open('w') as log:
    if i==0:
     with turn.turn():result=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,cwd=R,timeout=120)
    else:result=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,cwd=R,timeout=30)
   if result.returncode:raise RuntimeError('CPU phase failed '+str(i))
  raw=(d/'proof.log').read_text();proof=json.loads(raw);assert proof['passed'];deps={}
  for n in (d/'proof.d').read_text().replace('\\\n',' ').split(':',1)[1].split():
   p=Path(n).resolve();assert pins[str(p)]==sha(p);deps[str(p)]=sha(p)
  for n,h in pins.items():assert sha(n)==h,n
  assert sha(commands[0][0])==receipt['compiler_sha256'];assert sum(p.stat().st_size for p in d.rglob('*') if p.is_file())<=64*1024**2
  receipt.update(passed=True,proof=proof,dependencies=deps,binary_sha256=sha(d/'proof'),proof_log_sha256=sha(d/'proof.log'),compile_log_sha256=sha(d/'compile.log'),compile_turn_sha256=sha(coordinator))
 except BaseException as e:receipt['error']=repr(e);raise
 finally:(d/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 dest=P/'evidence/cpu-proof.json';assert not dest.exists();dest.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'passed':True,'receipt_sha256':sha(dest),'proof':receipt['proof']}))
