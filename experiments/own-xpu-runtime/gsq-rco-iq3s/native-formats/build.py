#!/usr/bin/env python3
"""Synthetic CPU qualification or separately admitted native compile-only."""
import argparse,hashlib,importlib.util,json,os,pathlib,resource,shlex,shutil,subprocess,sys,time
P=pathlib.Path(__file__).resolve().parent;ROOT=P.parents[3]
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32))
 assert all(os.environ.get(k)=='2' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'))
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
 assert shutil.disk_usage(ROOT).free-50*1024**2>=27_000_000_000,'root floor/write reservation'
def load_module(path,name):
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
FILES=('packed.hpp','device_formats.hpp','fixture.cpp','native_entry.cpp','build.py','source-pins.json')
def native_plan(attempt):
 parent=ROOT/'experiments/own-xpu-runtime/stage2/packet208-sycl-paired-projections/build_native.py';plan=load_module(parent,'p208_build').plan();cmd,link=plan['commands'];cmd=list(cmd);link=list(link)
 old=cmd[cmd.index('-o')+1];obj=str(attempt/'native.o');binary=str(attempt/'native-disabled');cmd[cmd.index('-c')+1]=str(P/'native_entry.cpp');cmd[cmd.index('-o')+1]=obj;cmd[cmd.index('-MF')+1]=str(attempt/'native.d');link[link.index(old)]=obj;link[link.index('-o')+1]=binary
 return [cmd,link],plan['objects'],binary

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--cpu',action='store_true');ap.add_argument('--plan-native',action='store_true');ap.add_argument('--compile-native',action='store_true');a=ap.parse_args();assert sum((a.cpu,a.plan_native,a.compile_native))==1
 if a.plan_native:
  commands,objects,binary=native_plan(P/'build/native-preview');print(json.dumps({'commands':commands,'objects':objects,'binary':binary,'executed':False},indent=2));return
 limits();pins=json.loads((P/'source-pins.json').read_text());sources={**pins['sources'],**{str(P/n):sha(P/n) for n in FILES}}
 for path,want in sources.items():assert sha(path)==want,path
 expected=(P.parent/'formats/formats.hpp').read_text().replace('#include "../../stage2/packet2/kernels/math.hpp"','// iq3 definitions supplied by the unchanged selected runtime headers.')
 assert (P/'device_formats.hpp').read_text()==expected,'device format copy drift'
 attempt=P/'build'/str(time.time_ns());attempt.mkdir(parents=True)
 for n in FILES:shutil.copy2(P/n,attempt/n)
 receipt={'passed':False,'attempt':str(attempt),'source_sha256':sources,'device_executed':False,'model_executed':False,'native_invoked':False,'mode':'cpu' if a.cpu else 'native-compile-only'}
 if a.cpu:
  objects=pins['host_objects'];binary=str(attempt/'cpu-fixture');commands=[['/usr/bin/g++','-std=c++20','-O2','-fopenmp','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-MMD','-MF',str(attempt/'cpu.d'),str(P/'fixture.cpp'),*objects,'-lcrypto','-o',binary]]
 else:commands,objects,binary=native_plan(attempt)
 receipt['objects']=objects;receipt['commands']=commands
 try:
  for path,want in objects.items():assert sha(path)==want,path
  receipt['compiler_sha256']=sha(commands[0][0])
  sys.modules['build_engine']=sys.modules[__name__];turn=load_module(ROOT/'experiments/own-xpu-runtime/ops/compile_turn.py','compile_turn')
  for i,cmd in enumerate(commands):
   with turn.turn(),(attempt/('compile-'+str(i)+'.log')).open('w') as log:
    result=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,cwd=ROOT,timeout=180 if a.cpu else 1200)
   assert result.returncode==0,'compile failed '+str(i)
  deps={}
  for f in attempt.glob('*.d'):
   for path in shlex.split(f.read_text().replace('\\\n',' ').split(':',1)[1]):
    p=str(pathlib.Path(path).resolve());deps[p]=sha(p)
  # All dependencies must be in the admitted historical closure or own files.
  for path,digest in deps.items():assert sources.get(path)==digest,'unbound dependency '+path
  receipt.update(dependencies=deps,binary=binary,binary_sha256=sha(binary))
  if a.cpu:
   with (attempt/'run.stdout').open('w') as out,(attempt/'run.stderr').open('w') as err:result=subprocess.run([binary],stdout=out,stderr=err,timeout=120)
   receipt['run_returncode']=result.returncode;assert result.returncode==0,'CPU fixture failed';receipt['result']=json.loads((attempt/'run.stdout').read_text());assert receipt['result']['passed']
  else:
   # Offline only. Never invoke, dlopen or enumerate through the produced ELF.
   text=subprocess.check_output(['/usr/bin/nm','-C','--defined-only',binary],text=True,timeout=60);(attempt/'symbols.log').write_text(text);assert ' T gsq_future_packed_submit' in text
   main=subprocess.check_output(['/usr/bin/objdump','-d','--disassemble=main',binary],text=True,timeout=60);(attempt/'main.asm').write_text(main);assert '$0x40,%eax' in main and 'call' not in main.split('<main>:')[-1]
   bundler='/opt/intel/oneapi/compiler/2026.0/bin/compiler/clang-offload-bundler';obj=str(attempt/'native.o')
   targets=subprocess.check_output([bundler,'-type=o','-list','-input='+obj],text=True,timeout=60).splitlines();device=[x for x in targets if x.startswith('sycl-spir64')];assert len(device)==1
   bc=attempt/'device.bc';subprocess.run([bundler,'-type=o','-unbundle','-targets='+device[0],'-input='+obj,'-output='+str(bc)],check=True,timeout=60)
   subprocess.run(['/opt/intel/oneapi/compiler/2026.0/bin/compiler/sycl-post-link','-symbols','-split=source','-o',str(attempt/'kernels.table'),str(bc)],check=True,timeout=120)
   entries='\n'.join(f.read_text() for f in attempt.glob('kernels*.sym'));assert 'PackedKernel' in entries
   for t in (12,13,18,23,42):assert 'ILj'+str(t)+'E' in entries,'missing kernel '+str(t)
   (attempt/'kernel-entries.log').write_text(entries);receipt['offline']={'main_exit64':True,'entries':entries.splitlines(),'device_image_sha256':sha(bc)}
  for path,want in {**sources,**objects,**deps}.items():assert sha(path)==want,'postbuild drift '+path
  assert sha(commands[0][0])==receipt['compiler_sha256'];receipt['passed']=True
  evidence=P/'evidence';evidence.mkdir(exist_ok=True);out=evidence/('cpu-proof.json' if a.cpu else 'native-compile.json');assert not out.exists(),'no overwrite';dump(out,receipt)
 except BaseException as e:receipt['error']=type(e).__name__+': '+str(e);raise
 finally:dump(attempt/'receipt.json',receipt)
 print(json.dumps({'passed':True,'attempt':str(attempt),'mode':receipt['mode']}))
if __name__=='__main__':main()
