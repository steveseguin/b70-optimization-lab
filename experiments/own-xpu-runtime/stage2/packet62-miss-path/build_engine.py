#!/usr/bin/env python3
"""CPU-only incremental build from packet61; no device discovery or execution."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];B=P/'build'
PARENT=P.parent/'packet61-spin-hcfusion'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert os.environ.get('OMP_NUM_THREADS')=='2'
 assert not list((P/'selections').glob('*/screen-seal.json'))
 (B/'tmp').mkdir(exist_ok=True);os.environ['TMPDIR']=str(B/'tmp')
 commands=[];sources={};artifacts={}
 def bind(path):sources[str(path.relative_to(ROOT))]=sha(path)
 def run(cmd,name):
  cmd=list(map(str,cmd));commands.append(dict(command=cmd,cwd=str(ROOT),name=name))
  with (B/(name+'.log')).open('w') as log:subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
  print(name,'PASS',flush=True)
 parent=json.loads((PARENT/'build-device-receipt.json').read_text())
 for name,digest in parent['sources'].items():assert sha(ROOT/name)==digest,name
 sources.update(parent['sources']);bind(PARENT/'build-device-receipt.json')
 from kernel_gate import mirror
 from math_gate import closure,check
 check();mapping=mirror()
 for path in closure():bind(path);bind(mapping[path])
 prior=json.loads((PARENT/'engine-commands.json').read_text())
 local=B/'engine';local.mkdir(exist_ok=True)
 (local/'main.cpp').write_text('#include '+json.dumps(str(mapping[P/'main.cpp']))+'\n')
 (local/'entry-main.cpp').write_text('#define main packet26_model_entry\n#include "main.cpp"\n#undef main\n')
 for mode in ('gnu-host','device'):
  dest=B/mode;dest.mkdir(exist_ok=True)
  base=next(x['command'] for x in prior if x['name']==mode+'-entry-main')
  base=base[:base.index('-o')];base=[x.replace(str(PARENT),str(P)) if x.startswith('-I') else x for x in base]
  for stem,src in (('entry-main',local/'entry-main.cpp'),('p49d_submit',mapping[P/'p49d_submit.cpp'])):
   run([*base,'-o',dest/(stem+'.o'),'-c',src],mode+'-'+stem)
  link=list(next(x['command'] for x in prior if x['name']==mode+'-link'));link[link.index('-o')+1]=str(dest/'own-rt-iq3')
  for i,arg in enumerate(link):
   if not arg.endswith('.o'):continue
   if arg==str(PARENT/'build'/mode/'entry-main.o'):link[i]=str(dest/'entry-main.o')
   elif arg.endswith('-p49d_submit.cpp.o'):link[i]=str(dest/'p49d_submit.o')
   else:
    src=Path(arg);bind(src)
    target=dest/'inherited'/(hashlib.sha256(str(src).encode()).hexdigest()[:12]+'-'+src.name);target.parent.mkdir(exist_ok=True)
    if not target.exists():os.link(src,target)
    assert sha(target)==sha(src);link[i]=str(target)
  run(link,mode+'-link');artifacts[str((dest/'own-rt-iq3').relative_to(P))]=sha(dest/'own-rt-iq3')
 # Exercise the same copy_lane body as SYCL, with production descriptor count.
 fixture_source=local/'flat_fixture.cpp';fixture_source.write_text((P/'flat_fixture.cpp').read_text())
 host_base=next(x['command'] for x in commands if x['name']=='gnu-host-entry-main');host_base=host_base[:host_base.index('-o')]
 run([*host_base,'-o',B/'flat-fixture.o','-c',fixture_source],'flat-fixture-compile')
 host_link=list(next(x['command'] for x in commands if x['name']=='gnu-host-link'))
 host_link=[x for x in host_link if not x.endswith('own-rt-iq3-entry.cpp.o')]
 host_link=[str(B/'flat-fixture.o') if x==str(B/'gnu-host/entry-main.o') else x for x in host_link]
 host_link[host_link.index('-o')+1]=str(B/'flat-fixture')
 run(host_link,'flat-fixture-link');artifacts['build/flat-fixture']=sha(B/'flat-fixture');bind(P/'flat_fixture.cpp')
 for path in local.iterdir():bind(path)
 for leaf in ('build_engine.py','kernel_gate.py','kernel_overlay.py','submission_overlay.py','math_gate.py','kernel_guard.hpp','host_spin.hpp','mtp-manifest.tsv','rope.bf16'):bind(P/leaf)
 save(P/'engine-commands.json',commands);bind(P/'engine-commands.json')
 assert sum(f.stat().st_size for f in B.rglob('*') if f.is_file())<400_000_000
 save(P/'build-device-receipt.json',dict(schema='packet62.lean-build.v1',passed=True,device_executed=False,
  sources=sources,artifacts=artifacts,unchanged_objects='Hardlinks to sealed packet61 compiler outputs; new entry and selection parser',nice=19,cpu_affinity=sorted(os.sched_getaffinity(0))))
 print('Engine built; no device execution',flush=True)
if __name__=='__main__':main()
