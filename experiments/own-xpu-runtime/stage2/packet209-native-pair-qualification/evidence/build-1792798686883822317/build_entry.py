"""Compile-only P209 entry; preserve P208 fixture/kernel object and device image."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,resource,shlex,shutil,subprocess,sys,time
P=Path(__file__).resolve().parent;ROOT=P.parents[3];OLD=P.parent/'packet208-sycl-paired-projections'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
SOURCES=('entry.cpp','native_guard.hpp','strict_json.hpp','build_entry.py','parent-pins.json')
FLOOR=27_000_000_000;RESERVE=256*1024**2

def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):assert os.environ.get(k)=='2'
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 assert shutil.disk_usage(ROOT).free-RESERVE>=FLOOR,'P209 compile floor'

def plan():
 baseline=json.loads((OLD/'evidence/build-compile-only.json').read_text());b=baseline['plan'];out=P/'build/native'
 compile=list(b['commands'][0]);link=list(b['commands'][1]);obj=str(out/'entry.o');binary=str(out/'paired-qualification');renamed=str(out/'p208-renamed.o')
 compile[compile.index('-c')+1]=str(P/'entry.cpp');compile[compile.index('-o')+1]=obj;compile[compile.index('-MF')+1]=str(out/'entry.d')
 link[link.index(b['object'])]=obj;link.insert(link.index(obj)+1,renamed);link[link.index('-o')+1]=binary
 return {'commands':[['/usr/bin/objcopy','--redefine-sym','main=p208_compile_only_main',b['object'],renamed],compile,link], 'binary':binary,'object':obj,'renamed_object':renamed,'original_object':b['object'],'objects':b['objects'],'depfile':str(out/'entry.d'),'parent_object_sha256':b['object_sha256'],'parent_device_image_sha256':baseline['offline_image']['bitcode_sha256'],'parent_receipt_sha256':sha(OLD/'evidence/build-compile-only.json')}

def execute(command,path,timeout=1800):
 with path.open('w') as stream:
  p=subprocess.run(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout)
 if p.returncode:raise RuntimeError(f'compile/inspection rc={p.returncode}: {path}')
 return path.read_text()

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--compile-only',action='store_true');a=ap.parse_args();limits();item=plan()
 if not a.compile_only:print(json.dumps(item,indent=2));return 0
 pins=json.loads((P/'parent-pins.json').read_text());before={str((P/n).relative_to(ROOT)):sha(P/n) for n in SOURCES}
 for path,want in pins.items():assert sha(ROOT/path)==want,path
 for path,want in item['objects'].items():assert sha(path)==want,path
 assert sha(item['original_object'])==item['parent_object_sha256']
 attempt=P/'evidence'/('build-'+str(time.time_ns()));attempt.mkdir(parents=True)
 for n in SOURCES:(attempt/n).write_bytes((P/n).read_bytes())
 (P/'build/native').mkdir(parents=True,exist_ok=True)
 receipt={'schema':'packet209.native-build.v1','passed':False,'compile_only':True,'device_enumerated':False,'device_executed':False,'plan':item,'source_sha256':before}
 sys.modules['build_engine']=sys.modules[__name__];sys.path.insert(0,str(ROOT/'experiments/own-xpu-runtime/ops'));from compile_turn import turn
 try:
  for i,cmd in enumerate(item['commands']):
   limits()
   with turn():execute(cmd,attempt/f'command-{i}.log')
  dependencies=Path(item['depfile']).read_text().replace('\\\n',' ');paths=[Path(x).resolve() for x in shlex.split(dependencies.split(':',1)[1])]
  inherited=json.loads((OLD/'evidence/build-compile-only.json').read_text())['plan']['repository_dependencies'];actual={}
  for path in paths:
   assert path.is_relative_to(ROOT),str(path)
   rel=str(path.relative_to(ROOT));digest=sha(path)
   if not path.is_relative_to(P):assert inherited.get(rel)==digest,'unbound dependency '+rel
   actual[rel]=digest
  bundler='/opt/intel/oneapi/compiler/2026.0/bin/compiler/clang-offload-bundler';bc=P/'build/native/p208-device.bc'
  execute([bundler,'-type=o','-unbundle','-targets=sycl-spir64-unknown-unknown','-input='+item['renamed_object'],'-output='+str(bc)],attempt/'unbundle.log',60)
  assert sha(bc)==item['parent_device_image_sha256'],'renaming changed device image'
  symbols=execute(['/usr/bin/nm','-C','--defined-only',item['binary']],attempt/'symbols.log',60)
  assert ' T p208_future_qualification' in symbols and ' T p208_compile_only_main' in symbols and ' T main' in symbols
  for path,want in {**pins,**before}.items():assert sha(ROOT/path)==want,path
  for path,want in item['objects'].items():assert sha(path)==want,path
  assert sha(item['original_object'])==item['parent_object_sha256']
  item.update(repository_dependencies=actual,binary_sha256=sha(item['binary']),entry_object_sha256=sha(item['object']),renamed_object_sha256=sha(item['renamed_object']))
  receipt.update(passed=True,device_image_sha256=sha(bc),device_image_bytes=bc.stat().st_size,offline_symbols_verified=True)
 except BaseException as ex:receipt['error']=f'{type(ex).__name__}: {ex}'
 finally:
  receipt['artifacts']={str(p.relative_to(ROOT)):sha(p) for p in attempt.iterdir() if p.is_file()}
  text=json.dumps(receipt,indent=2,sort_keys=True)+'\n';(attempt/'receipt.json').write_text(text)
  if receipt['passed']:(P/'evidence/build-compile-only.json').write_text(text)
 print(json.dumps({'passed':receipt['passed'],'attempt':str(attempt),'error':receipt.get('error')}));return 0 if receipt['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
