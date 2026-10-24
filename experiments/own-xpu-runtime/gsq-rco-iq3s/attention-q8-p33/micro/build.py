#!/usr/bin/env python3
"""Read-only command plan or explicit compile-only; never invoke the artifact."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,resource,shlex,shutil,subprocess,sys,time
P=Path(__file__).resolve().parent;L=P.parents[1];ROOT=L.parents[2]
CONTROL=L/'integration/evidence/full-native-build.json'
CONTROL_SHA='5d4643615ad94c0805de75ac7a01806dbb784c7fc09052f90ee04deafc5abd6d'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,j):p.write_text(json.dumps(j,indent=2)+'\n')
def module(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32))
 assert all(os.environ.get(k)=='2' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'))
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
 assert shutil.disk_usage(ROOT).free>=27_000_000_000+64*1024**2,'64MiB reservation above floor'
def plan(attempt):
 assert sha(CONTROL)==CONTROL_SHA;c=json.loads(CONTROL.read_text());assert c['passed']
 compile=list(c['commands'][0]);compile[compile.index('-c')+1]=str(P/'runner.cpp');compile[compile.index('-o')+1]=str(attempt/'micro.o');compile[compile.index('-MF')+1]=str(attempt/'micro.d')
 link=list(c['commands'][-1]);old=c['commands'][0][c['commands'][0].index('-o')+1];link[link.index(old)]=str(attempt/'micro.o');link[link.index('-o')+1]=str(attempt/'attention-micro')
 objects={p:h for p,h in c['object_sha256'].items() if p!=old};assert len(objects)==39 and all(p in link for p in objects)
 return c,[compile,link],objects
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--compile-only',action='store_true');a=ap.parse_args();attempt=P/'build'/str(time.time_ns());control,commands,objects=plan(attempt)
 if not a.compile_only:print(json.dumps({'commands':commands,'objects':objects,'native_invocation':False,'weight_reads':False},indent=2));return
 limits();assert not (P/'evidence/native-build.json').exists(),'no automatic rebuild'
 pins=json.loads((P/'source-pins.json').read_text());local={str(x):sha(x) for x in P.iterdir() if x.is_file() and x.suffix in ('.py','.hpp','.cpp','.json','.md') and x.name!='source-pins.json'};sources={**pins['source_sha256'],**local,str(P/'source-pins.json'):sha(P/'source-pins.json')}
 original={str((ROOT/Path(k)).resolve()) if not Path(k).is_absolute() else k:v for k,v in {**control['source_sha256'],**control['dependencies']}.items()}
 bound={**original,**sources,**objects}
 for p,h in bound.items():assert sha(p)==h,p
 attempt.mkdir(parents=True);receipt={'passed':False,'compile_only':True,'binary_invoked':False,'device_execution':False,'commands':commands,'source_sha256':sources,'objects_reused':objects,'control_build_sha256':CONTROL_SHA,'compiler_sha256':sha(commands[0][0])}
 for p in local:shutil.copy2(p,attempt/Path(p).name)
 def run(cmd,log):
  with (attempt/log).open('w') as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,cwd=ROOT,timeout=1200)
  assert r.returncode==0,log
  return (attempt/log).read_text()
 try:
  sys.modules['build_engine']=sys.modules[__name__];turn=module(ROOT/'experiments/own-xpu-runtime/ops/compile_turn.py','micro_turn')
  for i,cmd in enumerate(commands):
   with turn.turn():run(cmd,f'compile-{i}.log')
  deps={str(Path(p).resolve()):sha(p) for p in shlex.split((attempt/'micro.d').read_text().replace('\\\n',' ').split(':',1)[1])}
  for p,h in deps.items():assert bound.get(p)==h,'unbound dependency '+p
  binary=attempt/'attention-micro';symbols=run(['/usr/bin/nm','-C','--defined-only',str(binary)],'symbols.log')
  for needle in ('micro::run(', 'iq3::kopt::gemv(', 'p33::submit(', 'p33::Kernel<0u, (iq3::Type)8, 6144u, 1u>'):assert needle in symbols,needle
  run(['/usr/bin/objdump','-d','--disassemble=main',str(binary)],'main.asm')
  for p,h in bound.items():assert sha(p)==h,'postbuild drift '+p
  assert sha(commands[0][0])==receipt['compiler_sha256']
  receipt.update(passed=True,dependencies=deps,binary=str(binary),binary_sha256=sha(binary),object_sha256=sha(attempt/'micro.o'),offline={'symbols_sha256':sha(attempt/'symbols.log'),'main_asm_sha256':sha(attempt/'main.asm')})
  (P/'evidence').mkdir(exist_ok=True);dump(P/'evidence/native-build.json',receipt)
 except BaseException as e:receipt['error']=repr(e);raise
 finally:dump(attempt/'receipt.json',receipt)
 print(json.dumps({'passed':True,'binary_invoked':False,'attempt':str(attempt)}))
if __name__=='__main__':main()
