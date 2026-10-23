"""Compile/link/offline-inspect only. Never invokes the resulting native artifact."""
from pathlib import Path
import argparse,hashlib,json,os,resource,shlex,shutil,subprocess,time
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
SOURCES=('paired_sycl.hpp','native_fixture.cpp','selected_headers.hpp','build_native.py','parent-pins.json')
FLOOR=27_000_000_000;RESERVE=256*1024**2
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):assert os.environ.get(name)=='2'
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 assert shutil.disk_usage(ROOT).free-RESERVE>=FLOOR,'P208 compile floor/reservation'
def plan():
 parent=P.parent/'packet198-postreply-checkpoint/evidence/build-compile-only.json'
 baseline=next(r for r in json.loads(parent.read_text())['plans'] if r['target']=='device')
 compile=list(baseline['commands'][0]);link=list(baseline['commands'][1]);out=P/'build/native'
 old=compile[compile.index('-o')+1];obj=str(out/'native_fixture.o');binary=str(out/'paired-native-fixture')
 compile[compile.index('-o')+1]=obj;compile[compile.index('-c')+1]=str(P/'native_fixture.cpp');compile[compile.index('-MF')+1]=str(out/'native_fixture.d')
 # Main/fixture dispatch entry objects belong to the old application. Retain
 # its selected native arithmetic/owner/backend objects without a new Engine.
 objects={p:s for p,s in baseline['objects'].items() if not any(n in Path(p).name for n in ('own-rt-iq3-entry','entry-nongemv_fixture','entry-k2_fixture','_fixture.cpp','gemv_timing.cpp','gguf.cpp'))}
 removed=set(baseline['objects'])-set(objects);link=[x for x in link if x not in removed]
 assert link.count(old)==1;link[link.index(old)]=obj;link[link.index('-o')+1]=binary
 assert '-fsycl' in compile and '-DOWN_RT_HOST_ONLY' not in compile
 assert '-ffp-contract=off' in compile and '-fno-fast-math' in compile
 return {'target':'device-compile-only','commands':[compile,link],'objects':objects,'binary':binary,'object':obj,'depfile':str(out/'native_fixture.d'),'parent_build_receipt_sha256':sha(parent),'floor_bytes':FLOOR,'write_reservation_bytes':RESERVE}
def execute(command,path,timeout=1800):
 with path.open('w') as log:
  p=subprocess.run(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
 if p.returncode:raise RuntimeError(f'CPU build/inspection command failed rc={p.returncode}: {path}')
 return path.read_text()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--compile-only',action='store_true');a=ap.parse_args();limits();item=plan()
 if not a.compile_only:print(json.dumps({'executed':False,'plan':item},indent=2));return
 for p,w in json.loads((P/'parent-pins.json').read_text()).items():assert sha(ROOT/p)==w,p
 for p,w in item['objects'].items():assert sha(p)==w,p
 before={str((P/n).relative_to(ROOT)):sha(P/n) for n in SOURCES}
 attempt=P/'evidence'/('build-'+str(time.time_ns()));attempt.mkdir(parents=True)
 for n in SOURCES:(attempt/n).write_bytes((P/n).read_bytes())
 (P/'build/native').mkdir(parents=True,exist_ok=True)
 receipt={'schema':'packet208.native-build.v1','passed':False,'compile_only':True,'fixture_executed':False,'device_enumerated':False,'device_executed':False,'model_executed':False,'plan':item,'source_sha256':before}
 import sys
 sys.modules['build_engine']=sys.modules[__name__]
 sys.path.insert(0,str(ROOT/'experiments/own-xpu-runtime/ops'));from compile_turn import turn
 try:
  for i,cmd in enumerate(item['commands']):
   limits()
   with turn():execute(cmd,attempt/f'compile-{i}.log')
  deps=Path(item['depfile']).read_text().replace('\\\n',' ')
  paths=[Path(x).resolve() for x in shlex.split(deps.split(':',1)[1])]
  inherited=json.loads((ROOT/'experiments/own-xpu-runtime/ops/packet201-window/actual-cpu-plan.json').read_text())['profile']['source_sha256']
  actual={}
  for path in paths:
   assert path.is_relative_to(ROOT),str(path)
   relative=str(path.relative_to(ROOT));digest=sha(path)
   if not path.is_relative_to(P):assert inherited.get(relative)==digest,'unbound inherited compiler input: '+relative
   actual[relative]=digest
  for path,want in {**before,**json.loads((P/'parent-pins.json').read_text())}.items():assert sha(ROOT/path)==want,path
  for path,want in item['objects'].items():assert sha(path)==want,path
  item.update(repository_dependencies=actual,binary_sha256=sha(item['binary']),object_sha256=sha(item['object']))
  # These tools parse files offline; none loads or invokes the native artifact.
  symbols=execute(['/usr/bin/nm','-C','--defined-only',item['binary']],attempt/'native-symbols.log',60)
  assert ' T p208_future_qualification' in symbols,'qualification body missing from linked ELF'
  bundler='/opt/intel/oneapi/compiler/2026.0/bin/compiler/clang-offload-bundler'
  targets=execute([bundler,'-type=o','-list','-input='+item['object']],attempt/'offload-targets.log',60).splitlines()
  device=[t.strip() for t in targets if t.strip().startswith('sycl-spir64')]
  assert len(device)==1,targets
  bitcode=P/'build/native/pair-device.bc'
  execute([bundler,'-type=o','-unbundle','-targets='+device[0],'-input='+item['object'],'-output='+str(bitcode)],attempt/'unbundle.log',60)
  post='/opt/intel/oneapi/compiler/2026.0/bin/compiler/sycl-post-link';table=P/'build/native/pair-kernels.table'
  execute([post,'-symbols','-split=source','-o',str(table),str(bitcode)],attempt/'kernel-post-link.log',120)
  symbolfiles=list(table.parent.glob('pair-kernels*.sym'));kerneltext='\n'.join(p.read_text() for p in symbolfiles)
  assert 'NativePairKernel' in kerneltext and '10240' in kerneltext and '6144' in kerneltext,'missing compiled pair kernel entries'
  (attempt/'kernel-entries.log').write_text(kerneltext)
  sections=execute(['/usr/bin/readelf','-SW',item['binary']],attempt/'elf-sections.log',60)
  strings=execute(['/usr/bin/strings','-a',item['binary']],P/'build/native/linked-strings.log',60)
  assert 'NativePairKernel' in strings and '__sycl' in symbols,'linked SYCL image/registration missing'
  compiler=Path(item['commands'][0][0]);receipt.update(passed=True,compiler={'path':str(compiler),'realpath':str(compiler.resolve()),'sha256':sha(compiler)},offline_image={'targets':targets,'bitcode_sha256':sha(bitcode),'bitcode_bytes':bitcode.stat().st_size,'symbol_files':{str(p.relative_to(ROOT)):sha(p) for p in symbolfiles},'kernel_entries':kerneltext.splitlines(),'linked_qualification_symbol':True,'linked_sycl_registration':True})
 except Exception as ex:
  receipt['error']=f'{type(ex).__name__}: {ex}'
 finally:
  receipt['artifact_sha256']={str(p.relative_to(ROOT)):sha(p) for p in attempt.iterdir() if p.is_file()}
  (attempt/'receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
  if receipt['passed']:(P/'evidence/build-compile-only.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
 print(json.dumps({'passed':receipt['passed'],'attempt':str(attempt),'error':receipt.get('error')}));return 0 if receipt['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
