#!/usr/bin/env python3
"""Compile/offline inspect only; never invoke the qualification runner."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,resource,shlex,shutil,subprocess,sys,time
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def module(path,name):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32))
 assert all(os.environ.get(k)=='2' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'))
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
 assert shutil.disk_usage(ROOT).free-50*1024**2>=27_000_000_000,'root floor/reservation'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--compile-only',action='store_true');a=ap.parse_args();attempt=P/'build'/str(time.time_ns())
 parent=module(P.parent/'native-formats/build.py','packed_build');commands,objects,binary=parent.native_plan(attempt)
 commands[0][commands[0].index('-c')+1]=str(P/'runner.cpp');commands[1][commands[1].index('-o')+1]=str(attempt/'qualify-native');binary=str(attempt/'qualify-native')
 if not a.compile_only:print(json.dumps({'commands':commands,'objects':objects,'binary':binary,'executed':False},indent=2));return
 limits();pins=json.loads((P/'source-pins.json').read_text());sources={**pins['sources'],**{str(P/n):sha(P/n) for n in ('runner.cpp','build.py','source-pins.json')}}
 for p,h in {**sources,**objects}.items():assert sha(p)==h,p
 attempt.mkdir(parents=True)
 for n in ('runner.cpp','build.py','source-pins.json'):shutil.copy2(P/n,attempt/n)
 receipt={'passed':False,'compile_only':True,'device_executed':False,'runner_invoked':False,'attempt':str(attempt),'sources':sources,'objects':objects,'commands':commands,'compiler_sha256':sha(commands[0][0])}
 def execute(cmd,name,timeout=1200):
  with (attempt/name).open('w') as out:r=subprocess.run(cmd,stdout=out,stderr=subprocess.STDOUT,cwd=ROOT,timeout=timeout)
  assert r.returncode==0,'compile/inspection failed '+name
  return (attempt/name).read_text()
 try:
  sys.modules['build_engine']=sys.modules[__name__];turn=module(ROOT/'experiments/own-xpu-runtime/ops/compile_turn.py','turn')
  for i,cmd in enumerate(commands):
   with turn.turn():execute(cmd,'compile-'+str(i)+'.log')
  deps={str(Path(x).resolve()):sha(x) for x in shlex.split((attempt/'native.d').read_text().replace('\\\n',' ').split(':',1)[1])}
  for p,h in deps.items():assert sources.get(p)==h,'unbound dependency '+p
  symbols=execute(['/usr/bin/nm','-C','--defined-only',binary],'symbols.log',60);assert 'qualification::run(' in symbols
  execute(['/usr/bin/objdump','-d','--disassemble=main',binary],'main.asm',60)
  bundler='/opt/intel/oneapi/compiler/2026.0/bin/compiler/clang-offload-bundler';obj=attempt/'native.o';targets=execute([bundler,'-type=o','-list','-input='+str(obj)],'targets.log',60).splitlines();target=[t for t in targets if t.startswith('sycl-spir64')];assert len(target)==1
  bc=attempt/'device.bc';execute([bundler,'-type=o','-unbundle','-targets='+target[0],'-input='+str(obj),'-output='+str(bc)],'unbundle.log',60)
  execute(['/opt/intel/oneapi/compiler/2026.0/bin/compiler/sycl-post-link','-symbols','-split=source','-o',str(attempt/'kernels.table'),str(bc)],'post-link.log',120)
  entries='\n'.join(f.read_text() for f in attempt.glob('kernels*.sym'))
  for t in (12,13,18,23,42):assert 'PackedKernelILj'+str(t)+'E' in entries
  (attempt/'kernel-entries.log').write_text(entries)
  for p,h in {**sources,**objects,**deps}.items():assert sha(p)==h,'postbuild drift '+p
  assert sha(commands[0][0])==receipt['compiler_sha256']
  receipt.update(passed=True,dependencies=deps,binary=binary,binary_sha256=sha(binary),kernel_entries=entries.splitlines(),device_image_sha256=sha(bc))
  evidence=P/'evidence';evidence.mkdir(exist_ok=True);assert not (evidence/'compile-only.json').exists();dump(evidence/'compile-only.json',receipt)
 except BaseException as ex:receipt['error']=type(ex).__name__+': '+str(ex);raise
 finally:dump(attempt/'receipt.json',receipt)
 print(json.dumps({'passed':True,'attempt':str(attempt),'runner_invoked':False}))
if __name__=='__main__':main()
