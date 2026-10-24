#!/usr/bin/env python3
"""Synthetic GNU arithmetic only; no model/native-owner execution."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,resource,shlex,shutil,subprocess,sys,time
P=Path(__file__).resolve().parent;L=P.parent;ROOT=L.parents[2]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32))
 assert all(os.environ.get(k)=='2' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'))
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));resource.setrlimit(resource.RLIMIT_CORE,(0,0));assert shutil.disk_usage(ROOT).free>=27_000_000_000+32*1024**2

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--build',action='store_true');a=ap.parse_args();d=P/'build'/str(time.time_ns());binary=d/'cpu-proof'
 cmd=['/usr/bin/g++','-std=gnu++20','-O2','-g0','-fno-fast-math','-ffp-contract=off','-DHOST_ONLY','-DOWN_RT_HOST_ONLY','-MMD','-MF',str(d/'fixture.d'),str(P/'fixture.cpp'),'-o',str(binary)]
 if not a.build:print(json.dumps({'commands':[cmd,[str(binary)]],'synthetic_only':True,'executed':False},indent=2));return
 limits();assert not (P/'evidence/cpu-proof.json').exists(),'no automatic repetition'
 selection=json.loads((P/'selection.json').read_text());control=json.loads((L/'integration/evidence/full-native-build.json').read_text())
 pins={str((ROOT/Path(n)).resolve()):h for n,h in {**control['source_sha256'],**control['dependencies']}.items()}
 pins.update(selection['source_sha256'])
 for f in [P/'prepare.py',P/'selection.json',P/'fixture.cpp',P/'fixture_math.hpp',P/'build_cpu.py',ROOT/'experiments/own-xpu-runtime/ops/compile_turn.py']:pins[str(f)]=sha(f)
 for n,h in pins.items():assert sha(n)==h,n
 d.mkdir(parents=True);r={'passed':False,'commands':[cmd,[str(binary)]],'source_sha256':pins,'compiler_sha256':sha(cmd[0]),'native_executed':False,'model_payload_read':False}
 for name in ('prepare.py','selection.json','fixture.cpp','fixture_math.hpp','build_cpu.py'):shutil.copy2(P/name,d/name)
 try:
  sys.modules['build_engine']=sys.modules[__name__];s=importlib.util.spec_from_file_location('qkv_compile_turn',ROOT/'experiments/own-xpu-runtime/ops/compile_turn.py');turn=importlib.util.module_from_spec(s);s.loader.exec_module(turn)
  for i,command in enumerate((cmd,[str(binary)])):
   with turn.turn(),(d/f'command-{i}.log').open('w') as f:out=subprocess.run(command,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,cwd=ROOT,timeout=180)
   assert out.returncode==0,'bounded synthetic command failed '+str(i)
  deps={str(Path(x).resolve()):sha(x) for x in shlex.split((d/'fixture.d').read_text().replace('\\\n',' ').split(':',1)[1])}
  for n,h in deps.items():assert pins.get(n)==h,'unbound dependency '+n
  proof=json.loads((d/'command-1.log').read_text());assert proof['passed'] and not proof['mismatches']
  for n,h in pins.items():assert sha(n)==h,'postproof drift '+n
  assert sha(cmd[0])==r['compiler_sha256'];r.update(passed=True,proof=proof,binary_sha256=sha(binary),dependencies=deps)
  (P/'evidence/cpu-proof.json').write_text(json.dumps(r,indent=2)+'\n')
 except BaseException as e:r['error']=repr(e);raise
 finally:(d/'receipt.json').write_text(json.dumps(r,indent=2)+'\n')
 print(json.dumps({'passed':True,'receipt_sha256':sha(P/'evidence/cpu-proof.json'),'attempt':str(d)}))
if __name__=='__main__':main()
