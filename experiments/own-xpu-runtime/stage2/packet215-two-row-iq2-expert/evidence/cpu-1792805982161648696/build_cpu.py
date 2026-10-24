"""Compile/run the reviewed standalone synthetic HOST_ONLY arithmetic fixture."""
from pathlib import Path
import argparse,hashlib,json,os,resource,shlex,shutil,subprocess,sys,time,traceback
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
P210=P.parent/'packet210-host-cache-chunk';P214=P.parent/'packet214-frozen-table-publication'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
SOURCES=('paired_iq2.hpp','selected_cpu.hpp','fixture.cpp','build_cpu.py','parent-pins.json')
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert all(os.environ.get(k)=='2' for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'))
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 assert shutil.disk_usage(ROOT).free>=27_000_000_000+128*1024**2

def selected_header():
 source=P.parent/'packet181-session-swap-v3/one-card/lineage/native/generated/p58ag_expert.hpp'
 matches=list((P.parent/'packet181-session-swap-v3/one-card/native-source').rglob('p49d_expert.hpp'));assert len(matches)==1;selected=matches[0]
 text=source.read_text();old=next(line for line in text.splitlines() if line.startswith('#include') and line.endswith('/p49d_expert.hpp"'))
 new='#include "'+str(selected)+'"';assert text.count(old)==1
 output=P/'build/selected-p58ag.hpp';output.parent.mkdir(parents=True,exist_ok=True);output.write_text(text.replace(old,new))
 return {'source':str(source.relative_to(ROOT)),'source_sha256':sha(source),'output':str(output.relative_to(ROOT)),'output_sha256':sha(output),'old_include':old,'new_include':new,'include_replacements':1,'arithmetic_unchanged':True}

def plan():
 spec=json.loads((P210/'production-binding.json').read_text());binary=P/'build/paired-iq2-fixture';dep=binary.with_suffix('.d')
 command=['/usr/bin/g++','-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-fopenmp','-DOWN_RT_HOST_ONLY','-MMD','-MF',str(dep),str(P/'fixture.cpp'),*spec['object_sha256'],'-lcrypto','-o',str(binary)]
 return {'compile_command':command,'object_sha256':spec['object_sha256'],'binary':str(binary),'depfile':str(dep),'run_command':[str(binary)],'run_timeout_seconds':180,'write_reservation_bytes':128*1024**2,'root_floor_bytes':27_000_000_000}

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run-host-only',action='store_true');args=ap.parse_args();limits();item=plan()
 pins=json.loads((P/'parent-pins.json').read_text())
 for path,want in pins.items():assert sha(ROOT/path)==want,path
 for path,want in item['object_sha256'].items():assert sha(path)==want,path
 if not args.run_host_only:print(json.dumps({'executed':False,'plan':item},indent=2));return
 before={str((P/name).relative_to(ROOT)):sha(P/name) for name in SOURCES}
 attempt=P/'evidence'/('cpu-'+str(time.time_ns()));attempt.mkdir(parents=True)
 for name in SOURCES:shutil.copyfile(P/name,attempt/name)
 receipt={'schema':'packet215.cpu-arithmetic-build.v1','passed':False,'device_executed':False,'model_executed':False,'native_executed':False,'source_sha256':before,'parent_sha256':pins,'plan':item,'attempt':str(attempt.relative_to(ROOT)),'compiler_sha256':sha('/usr/bin/g++')}
 sys.path.insert(0,str(ROOT/'experiments/own-xpu-runtime/ops'));from compile_turn import turn
 sys.modules['build_engine']=sys.modules[__name__]
 try:
  relocation=selected_header();receipt['selected_header']=relocation;shutil.copyfile(ROOT/relocation['output'],attempt/'selected-p58ag.hpp')
  with turn(),(attempt/'compile.log').open('w') as log:cp=subprocess.run(item['compile_command'],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=180)
  item['compile_returncode']=cp.returncode;assert cp.returncode==0,'CPU fixture compile failed'
  approved=dict(json.loads((ROOT/'experiments/own-xpu-runtime/ops/packet201-window/actual-cpu-plan.json').read_text())['profile']['source_sha256']);approved.update(json.loads((P210/'production-binding.json').read_text())['source_sha256']);approved.update(json.loads((P214/'evidence/build-compile-only.json').read_text())['plan']['repository_dependencies']);approved.update(pins);approved.update(before);approved[relocation['output']]=relocation['output_sha256']
  dependencies={}
  for path in [Path(x).resolve() for x in shlex.split(Path(item['depfile']).read_text().replace('\\\n',' ').split(':',1)[1])]:
   relative=str(path.relative_to(ROOT));digest=sha(path);assert approved.get(relative)==digest,'unbound compiler input '+relative;dependencies[relative]=digest
  item.update(repository_dependencies=dependencies,binary_sha256=sha(item['binary']))
  for path,want in {**dependencies,**before,**pins}.items():assert sha(ROOT/path)==want,path
  for path,want in item['object_sha256'].items():assert sha(path)==want,path
  with (attempt/'stdout.json').open('w') as out,(attempt/'stderr.log').open('w') as err:cp=subprocess.run(item['run_command'],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=out,stderr=err,timeout=item['run_timeout_seconds'])
  item['run_returncode']=cp.returncode;assert cp.returncode==0,'CPU arithmetic fixture failed'
  proof=json.loads((attempt/'stdout.json').read_text());assert proof['passed'];item['proof_sha256']=sha(attempt/'stdout.json')
  for path,want in {**dependencies,**before,**pins}.items():assert sha(ROOT/path)==want,path
  for path,want in item['object_sha256'].items():assert sha(path)==want,path
  assert sha(item['binary'])==item['binary_sha256'];assert sha('/usr/bin/g++')==receipt['compiler_sha256'];receipt['passed']=True
 except BaseException as exc:receipt['error']=repr(exc);(attempt/'failure.log').write_text(traceback.format_exc());raise
 finally:
  receipt['artifact_sha256']={str(f.relative_to(ROOT)):sha(f) for f in attempt.iterdir() if f.is_file()}
  (attempt/'receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
  if receipt['passed']:
   shutil.copyfile(attempt/'stdout.json',P/'evidence/arithmetic-proof.json');(P/'evidence/cpu-build.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
 print(json.dumps({'passed':True,'attempt':str(attempt),'proof_sha256':item['proof_sha256']}))
if __name__=='__main__':main()
