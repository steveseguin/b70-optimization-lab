"""Compile-only new HOST_ONLY Engine entry; no device target or execution path."""
from pathlib import Path
import argparse,hashlib,json,os,resource,shlex,subprocess,sys,time
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):assert os.environ.get(name)=='2'
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
def plan():
 parent=P.parent/'packet198-postreply-checkpoint/evidence/build-compile-only.json'
 p=next(x for x in json.loads(parent.read_text())['plans'] if x['target']=='host')
 compile=list(p['commands'][0]);link=list(p['commands'][1]);out=P/'build/host'
 old=compile[compile.index('-o')+1];new=str(out/'entry-main.o')
 compile[compile.index('-o')+1]=new;compile[compile.index('-c')+1]=str(P/'build/native/entry-main.cpp');compile[compile.index('-MF')+1]=str(out/'entry-main.d')
 assert link.count(old)==1;link[link.index(old)]=new;link[link.index('-o')+1]=str(out/'own-rt-iq3')
 assert '-DOWN_RT_HOST_ONLY' in compile
 return {'target':'host','commands':[compile,link],'objects':p['objects'],'binary':str(out/'own-rt-iq3'),'depfile':str(out/'entry-main.d'),'parent_build_receipt_sha256':sha(parent)}
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--compile-only',action='store_true');a=ap.parse_args();limits();item=plan()
 if not a.compile_only:print(json.dumps({'executed':False,'plans':[item]},indent=2));return
 from source_overlay import generate
 overlay=generate()
 sys.path.insert(0,str(ROOT/'experiments/own-xpu-runtime/ops'));from compile_turn import turn
 sys.modules['build_engine']=sys.modules[__name__]
 attempt=P/'evidence'/('build-'+str(time.time_ns()));attempt.mkdir()
 for name in ('source_overlay.py','chunk_runtime.hpp','paired_projection.hpp','pair_proof.hpp','build_engine.py'):(attempt/name).write_bytes((P/name).read_bytes())
 (attempt/'source-overlay.json').write_text(json.dumps(overlay,indent=2,sort_keys=True)+'\n')
 for path,want in item['objects'].items():assert sha(path)==want,path
 out=P/'build/host';out.mkdir(parents=True,exist_ok=True)
 row={'schema':'packet207.host-build.v1','passed':False,'compile_only':True,'device_executed':False,'model_executed':False,'plans':[item],'source_overlay_sha256':sha(P/'evidence/source-overlay.json')}
 for index,command in enumerate(item['commands']):
  with turn(),(attempt/f'compile-{index}.log').open('w') as log:
   cp=subprocess.run(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
  if cp.returncode:
   row.update(failed_command=index,returncode=cp.returncode);(attempt/'receipt.json').write_text(json.dumps(row,indent=2)+'\n');print(attempt);return cp.returncode
 deps=Path(item['depfile']).read_text().replace('\\\n',' ');paths=[Path(s) for s in shlex.split(deps.split(':',1)[1])]
 inherited=json.loads((ROOT/'experiments/own-xpu-runtime/ops/packet201-window/actual-cpu-plan.json').read_text())['profile']['source_sha256']
 actual={}
 for path in paths:
  path=path.resolve();assert path.is_relative_to(ROOT),str(path)
  relative=str(path.relative_to(ROOT));digest=sha(path)
  if not path.is_relative_to(P):assert inherited.get(relative)==digest,'unbound inherited compiler input: '+relative
  actual[relative]=digest
 for path,want in overlay['parent_source_sha256'].items():assert sha(ROOT/path)==want,path
 for path,want in overlay['source_sha256'].items():assert sha(ROOT/path)==want,path
 for path,want in overlay['outputs'].items():assert sha(P/path)==want,path
 for path,want in item['objects'].items():assert sha(path)==want,path
 item.update(repository_dependencies=actual,binary_sha256=sha(item['binary']))
 row.update(passed=True,source_sha256={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('source_overlay.py','chunk_runtime.hpp','paired_projection.hpp','pair_proof.hpp','build_engine.py')})
 (attempt/'receipt.json').write_text(json.dumps(row,indent=2,sort_keys=True)+'\n');(P/'evidence/build-compile-only.json').write_text(json.dumps(row,indent=2,sort_keys=True)+'\n');print(json.dumps({'passed':True,'binary':item['binary']}));return 0
if __name__=='__main__':raise SystemExit(main())
