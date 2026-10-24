"""Compile/link/offline-inspect only. Never invokes the resulting native artifact."""
from pathlib import Path
import argparse,hashlib,json,os,resource,shlex,shutil,subprocess,time
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
SOURCES=('publication.hpp','source_overlay.py','build_native.py','parent-pins.json')
FLOOR=27_000_000_000;RESERVE=768*1024**2
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):assert os.environ.get(name)=='2'
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 assert shutil.disk_usage(ROOT).free-RESERVE>=FLOOR,'P214 compile floor/reservation'
def plan():
 parent=P.parent/'packet198-postreply-checkpoint/evidence/build-compile-only.json'
 baseline=next(r for r in json.loads(parent.read_text())['plans'] if r['target']=='device')
 compile=list(baseline['commands'][0]);link=list(baseline['commands'][1]);out=P/'build/native'
 old=compile[compile.index('-o')+1];obj=str(out/'entry-main.o');binary=str(out/'production-prefill-disabled')
 compile[compile.index('-o')+1]=obj;compile[compile.index('-c')+1]=str(out/'entry-main.cpp');compile[compile.index('-MF')+1]=str(out/'entry-main.d')
 # Main/fixture dispatch entry objects belong to the old application. Retain
 # its selected native arithmetic/owner/backend objects and GGUF reader for the retained future Engine body.
 objects={p:s for p,s in baseline['objects'].items() if not any(n in Path(p).name for n in ('own-rt-iq3-entry','entry-nongemv_fixture','entry-k2_fixture'))}
 removed=set(baseline['objects'])-set(objects);link=[x for x in link if x not in removed]
 assert link.count(old)==1;link[link.index(old)]=obj;link[link.index('-o')+1]=binary
 assert '-fsycl' in compile and '-DOWN_RT_HOST_ONLY' not in compile
 assert '-ffp-contract=off' in compile and '-fno-fast-math' in compile
 return {'target':'device-compile-only','commands':[compile,link],'objects':objects,'binary':binary,'object':obj,'depfile':str(out/'entry-main.d'),'parent_build_receipt_sha256':sha(parent),'floor_bytes':FLOOR,'write_reservation_bytes':RESERVE}
def backend_provenance(item):
 lineage=P.parent/'packet181-session-swap-v3/one-card/lineage'
 source=lineage/'native/generated/single_device.cpp'
 historical=json.loads((lineage/'build-receipt.json').read_text())
 inputs=json.loads((lineage/'build-inputs.json').read_text())
 source_key='experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/build/native/single_device.cpp'
 object_key='experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/build/device/single_device.o'
 # Search the receipt's named digest maps, not arbitrary prose occurrences.
 maps=[v for v in historical.values() if isinstance(v,dict)]
 assert any(m.get(source_key)==sha(source) for m in maps),'backend source lineage mismatch'
 obj=next(Path(x) for x in item['objects'] if Path(x).name=='9a4184a797f41977-single_device.o')
 digest=sha(obj)
 assert any(m.get(object_key)==digest for m in maps),'backend object lineage mismatch'
 rows=[v for v in inputs.values() if isinstance(v,dict)]
 assert any(m.get('build/objects/'+obj.name,{}).get('sha256')==digest for m in rows),'copied backend object mismatch'
 return {'source':str(source.relative_to(ROOT)),'source_sha256':sha(source),'object':str(obj.relative_to(ROOT)),'object_sha256':digest,'lineage_receipt_sha256':sha(lineage/'build-receipt.json'),'copy_inputs_sha256':sha(lineage/'build-inputs.json'),'ordering_scope':'source-derived ordered compute queue plus CopyEngine BCS barrier; not executed'}
def execute(command,path,timeout=1800):
 with path.open('w') as log:
  p=subprocess.run(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
 if p.returncode:raise RuntimeError(f'CPU build/inspection command failed rc={p.returncode}: {path}')
 return path.read_text()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--compile-only',action='store_true');ap.add_argument('--prepare-only',action='store_true');a=ap.parse_args();limits();item=plan()
 assert not (a.compile_only and a.prepare_only)
 if not (a.compile_only or a.prepare_only):print(json.dumps({'executed':False,'plan':item},indent=2));return
 for p,w in json.loads((P/'parent-pins.json').read_text()).items():assert sha(ROOT/p)==w,p
 for p,w in item['objects'].items():assert sha(p)==w,p
 before={str((P/n).relative_to(ROOT)):sha(P/n) for n in SOURCES}
 attempt=P/'evidence'/('build-'+str(time.time_ns()));attempt.mkdir(parents=True)
 for n in SOURCES:(attempt/n).write_bytes((P/n).read_bytes())
 (P/'build/native').mkdir(parents=True,exist_ok=True)
 receipt={'schema':'packet214.native-build.v1','passed':False,'compile_only':True,'fixture_executed':False,'public_entry_disabled':True,'device_enumerated':False,'device_executed':False,'model_executed':False,'plan':item,'source_sha256':before}
 import sys
 sys.modules['build_engine']=sys.modules[__name__]
 sys.path.insert(0,str(ROOT/'experiments/own-xpu-runtime/ops'));from compile_turn import turn
 try:
  import source_overlay
  generated=source_overlay.generate()
  receipt['generated']=generated
  for name in ('main.cpp','checkpoint.hpp','request_front.hpp','entry-main.cpp'):(attempt/name).write_bytes((P/'build/native'/name).read_bytes())
  receipt['backend_provenance']=backend_provenance(item)
  if a.prepare_only:
   receipt.update(passed=True,prepared_only=True,compiled=False)
   return 0
  for i,cmd in enumerate(item['commands']):
   limits()
   with turn():execute(cmd,attempt/f'compile-{i}.log')
  deps=Path(item['depfile']).read_text().replace('\\\n',' ')
  paths=[Path(x).resolve() for x in shlex.split(deps.split(':',1)[1])]
  inherited=json.loads((ROOT/'experiments/own-xpu-runtime/ops/packet201-window/actual-cpu-plan.json').read_text())['profile']['source_sha256']
  inherited.update(json.loads((P.parent/'packet208-sycl-paired-projections/evidence/build-compile-only.json').read_text())['plan']['repository_dependencies'])
  inherited.update(json.loads((P.parent/'packet213-production-prefill-control/evidence/build-compile-only.json').read_text())['plan']['repository_dependencies'])
  inherited.update(json.loads((P/'parent-pins.json').read_text()))
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
  assert ' T p214_future_entry' in symbols and ' T main' in symbols,'disabled entry/future Engine body missing from linked ELF'
  main_disassembly=execute(['/usr/bin/objdump','-d','--disassemble=main',item['binary']],attempt/'public-main-disassembly.log',60)
  assert '<main>:' in main_disassembly and 'p214_future_entry' not in main_disassembly and 'p214_model_body' not in main_disassembly,'public main unexpectedly calls future body'
  assert '$0x40,%eax' in main_disassembly.replace(' ',''),'public main lacks exit64 return constant'
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
  if receipt['passed']:(P/'evidence'/('build-preparation.json' if a.prepare_only else 'build-compile-only.json')).write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
 print(json.dumps({'passed':receipt['passed'],'attempt':str(attempt),'error':receipt.get('error')}));return 0 if receipt['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
