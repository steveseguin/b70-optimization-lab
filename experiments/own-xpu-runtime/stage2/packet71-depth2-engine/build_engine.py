#!/usr/bin/env python3
"""Serial host-only rebuild of entry objects; reuse unchanged packet61x kernels."""
import hashlib,json,os,resource,shutil,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];B=P/'build'
BASE=P.with_name('packet64-record-bundle')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert os.environ.get('OMP_NUM_THREADS')=='2'
 assert not (P/'screen-seal.json').exists()
 assert shutil.disk_usage(ROOT).free>=12*1024**3
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 (B/'tmp').mkdir(parents=True,exist_ok=True);os.environ['TMPDIR']=str(B/'tmp')
 if not (B/'fusion-rope.hpp').exists():os.link(BASE/'build/fusion-rope.hpp',B/'fusion-rope.hpp')
 commands=[];sources={};artifacts={}
 def bind(p):sources[str(p.relative_to(ROOT))]=sha(p)
 parent=json.loads((BASE/'build-device-receipt.json').read_text())
 for name,digest in parent['sources'].items():assert sha(ROOT/name)==digest,name
 sources.update(parent['sources']);bind(BASE/'build-device-receipt.json')
 from kernel_gate import mirror
 from math_gate import closure
 mapping=mirror()
 for p in closure():bind(p);bind(mapping[p])
 prior=json.loads((BASE/'engine-commands.json').read_text())
 local=B/'engine';local.mkdir(exist_ok=True)
 (local/'main.cpp').write_text('#include '+json.dumps(str(mapping[P/'main.cpp']))+'\n')
 (local/'entry-main.cpp').write_text('#define main packet26_model_entry\n#include "main.cpp"\n#undef main\n')
 def run(cmd,name):
  assert shutil.disk_usage(ROOT).free>=12*1024**3
  assert sum(p.stat().st_size for p in B.rglob('*') if p.is_file())<1_000_000_000
  cmd=list(map(str,cmd));commands.append(dict(command=cmd,cwd=str(ROOT),name=name))
  with (B/(name+'.log')).open('w') as log:subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,stdin=subprocess.DEVNULL)
  print(name,'PASS',flush=True)
 # GNU and Intel host fixtures; no mini model or device execution.
 for mode,compiler in [('gnu-host','/usr/bin/g++'),('intel-host','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  cmd=next(x['command'] for x in prior if x['name']=='gnu-host-entry-main');cmd=[x.replace(str(BASE),str(P)) if x.startswith('-I') else x for x in cmd[:cmd.index('-o')]];cmd[0]=compiler
  run([*cmd,'-ffunction-sections','-fdata-sections','-Wl,--gc-sections',mapping[P/'batch_fixture.cpp'],'-o',B/(mode+'-batch-fixture')],mode+'-fixture-compile')
  artifacts['build/'+mode+'-batch-fixture']=sha(B/(mode+'-batch-fixture'))
 for mode in ('gnu-host','device'):
  dest=B/mode;dest.mkdir(exist_ok=True)
  cmd=next(x['command'] for x in prior if x['name']==mode+'-entry-main');cmd=cmd[:cmd.index('-o')]
  cmd=[x.replace(str(BASE),str(P)) if x.startswith('-I') else x for x in cmd]
  run([*cmd,'-o',dest/'entry-main.o','-c',local/'entry-main.cpp'],mode+'-entry-main')
  link=list(next(x['command'] for x in prior if x['name']==mode+'-link'));link[link.index('-o')+1]=str(dest/'own-rt-iq3')
  for i,arg in enumerate(link):
   if not arg.endswith('.o'):continue
   if arg==str(BASE/'build'/mode/'entry-main.o'):link[i]=str(dest/'entry-main.o')
   else:
    src=Path(arg);bind(src);target=dest/'inherited'/(hashlib.sha256(str(src).encode()).hexdigest()[:12]+'-'+src.name);target.parent.mkdir(exist_ok=True)
    if not target.exists():os.link(src,target)
    assert sha(src)==sha(target);link[i]=str(target)
  run(link,mode+'-link');artifacts[str((dest/'own-rt-iq3').relative_to(P))]=sha(dest/'own-rt-iq3')
 for p in local.iterdir():bind(p)
 for name in ('build_engine.py','kernel_gate.py','kernel_overlay.py','submission_overlay.py','math_gate.py','kernel_guard.hpp','mtp-manifest.tsv','rope.bf16','selection-decision.json','parent-source-manifest.json','packet68c-import.json','kernel-table.tsv'):bind(P/name)
 save(P/'engine-commands.json',commands);bind(P/'engine-commands.json')
 size=sum(p.stat().st_size for p in B.rglob('*') if p.is_file());assert size<1_000_000_000
 save(P/'build-device-receipt.json',dict(schema='packet71.lean-build.v1',passed=True,device_executed=False,sources=sources,artifacts=artifacts,logical_build_bytes=size,commands=commands,compiler_version=subprocess.check_output(['/opt/intel/oneapi/compiler/latest/bin/icpx','--version'],text=True),max_address_space_bytes=8*1024**3,nice=19,cpu_affinity=sorted(os.sched_getaffinity(0))))
if __name__=='__main__':main()
