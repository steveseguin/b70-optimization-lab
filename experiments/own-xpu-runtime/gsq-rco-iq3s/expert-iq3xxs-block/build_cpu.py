#!/usr/bin/env python3
"""Bounded synthetic CPU proof only; explicit --build, no native entry."""
import argparse,hashlib,importlib.util,json,os,resource,shlex,shutil,subprocess,sys,time
from pathlib import Path
P=Path(__file__).resolve().parent;L=P.parent;R=L.parents[2]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32))
 assert all(os.environ.get(k)=='2' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'))
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_FSIZE,(64*1024**2,64*1024**2))
 assert shutil.disk_usage(R).free>=27000000000+64*1024**2,'root floor +64MiB reservation'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--build',action='store_true');a=ap.parse_args()
 parent=L/'native-formats/source-pins.json';pins=json.loads(parent.read_text());objects=pins['host_objects'];files=[P/n for n in ('block.hpp','proof.cpp','selection.hpp','selection.json','source-pins.json','build_cpu.py')]
 sources={**pins['sources'],**{str((R/f).resolve()):h for f,h in json.loads((P/'source-pins.json').read_text()).items()},**{str(f):sha(f) for f in files},str(parent):sha(parent)}
 turnpath=R/'experiments/own-xpu-runtime/ops/compile_turn.py';sources[str(turnpath)]=sha(turnpath)
 d=P/'build'/str(time.time_ns());binary=d/'proof';cmd=['/usr/bin/g++','-std=c++20','-O2','-g0','-fopenmp','-fno-fast-math','-ffp-contract=off','-DHOST_ONLY','-MMD','-MF',str(d/'proof.d'),str(P/'proof.cpp'),*objects,'-lcrypto','-o',str(binary)]
 if not a.build:print(json.dumps(dict(commands=[cmd,[str(binary)]],executed=False,synthetic_only=True),indent=2));return
 limits();assert not (P/'evidence/cpu-proof.json').exists(),'no automatic proof rerun'
 for f,h in {**sources,**objects}.items():assert sha(f)==h,f
 d.mkdir(parents=True)
 for f in files:shutil.copy2(f,d/f.name)
 receipt=dict(passed=False,commands=[cmd,[str(binary)]],source_sha256=sources,objects=objects,compiler_sha256=sha(cmd[0]),attempt=str(d),native_executed=False,model_payload_read=False,device_constructed=False)
 try:
  sys.modules['build_engine']=sys.modules[__name__];spec=importlib.util.spec_from_file_location('iq3block_compile_turn',turnpath);turn=importlib.util.module_from_spec(spec);spec.loader.exec_module(turn)
  with turn.turn(),(d/'compile.log').open('w') as log:r=subprocess.run(cmd,cwd=R,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=180)
  assert r.returncode==0,'CPU compile failed'
  deps={str(Path(f).resolve()):sha(f) for f in shlex.split((d/'proof.d').read_text().replace('\\\n',' ').split(':',1)[1])}
  for f,h in deps.items():assert sources.get(f)==h,'unbound CPU dependency '+f
  with (d/'stdout.log').open('w') as out,(d/'stderr.log').open('w') as err:r=subprocess.run([str(binary)],cwd=d,stdin=subprocess.DEVNULL,stdout=out,stderr=err,timeout=180)
  receipt['run_returncode']=r.returncode;assert r.returncode==0,'exact CPU delta proof failed'
  proof=json.loads((d/'stdout.log').read_text());assert proof['passed'] is True
  for f,h in {**sources,**objects}.items():assert sha(f)==h,'postproof drift '+f
  assert sha(cmd[0])==receipt['compiler_sha256'];size=sum(f.stat().st_size for f in d.iterdir() if f.is_file());assert size<64*1024**2,'retained write budget'
  receipt.update(passed=True,proof=proof,dependencies=deps,binary_sha256=sha(binary),retained_bytes=size)
  (P/'evidence/cpu-proof.json').write_text(json.dumps(receipt,indent=2)+'\n')
 except BaseException as e:receipt['error']=repr(e);raise
 finally:(d/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps(dict(passed=True,receipt_sha256=sha(P/'evidence/cpu-proof.json'),attempt=str(d))))
if __name__=='__main__':main()
