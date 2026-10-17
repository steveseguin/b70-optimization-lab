#!/usr/bin/env python3
"""Packet63 CPU-only incremental compile; never alter inherited compiler objects."""
import hashlib,json,os,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent; ROOT=P.parents[3]; B=P/'build'
BASE=P.parent/'packet61x-spin-hcfusion-wait'; DRAFT=P.parent/'packet59c-draft-select'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert os.environ.get('OMP_NUM_THREADS')=='2'
def main():
 limits(); assert not list((P/'selections').glob('*/screen-seal.json'))
 assert not (P/'build-device-receipt.json').exists(),'fresh build only'
 (B/'tmp').mkdir(exist_ok=True);os.environ['TMPDIR']=str(B/'tmp')
 if not (B/'fusion-rope.hpp').exists():os.link(BASE/'build/fusion-rope.hpp',B/'fusion-rope.hpp')
 sources={}; artifacts={}; commands=[]; inherited=[]
 def bind(f):sources[str(f.relative_to(ROOT))]=sha(f)
 def run(command,name):
  command=list(map(str,command));commands.append(dict(name=name,command=command,cwd=str(ROOT)))
  with (B/(name+'.log')).open('w') as log:subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
  print(name,'PASS',flush=True)
 parent=json.loads((BASE/'build-device-receipt.json').read_text())
 for n,h in parent['sources'].items():assert sha(ROOT/n)==h,n
 sources.update(parent['sources']);bind(BASE/'build-device-receipt.json')
 from kernel_gate import mirror
 from math_gate import closure,check
 check();mapping=mirror()
 for f in closure():bind(f);bind(mapping[f])
 local=B/'engine';local.mkdir()
 (local/'entry-main.cpp').write_text('#define main packet26_model_entry\n#include '+json.dumps(str(mapping[P/'main.cpp']))+'\n#undef main\n')
 prior=json.loads((BASE/'engine-commands.json').read_text())
 for mode in ('gnu-host','device'):
  dest=B/mode;dest.mkdir();base=next(r['command'] for r in prior if r['name']==mode+'-entry-main')
  base=base[:base.index('-o')];base=[x.replace(str(BASE),str(P)) if x.startswith('-I') else x for x in base]
  for stem,src in [('entry-main',local/'entry-main.cpp'),('p49d_submit',mapping[P/'p49d_submit.cpp'])]:
   run([*base,'-o',dest/(stem+'.o'),'-c',src],mode+'-'+stem)
  link=list(next(r['command'] for r in prior if r['name']==mode+'-link'));link[link.index('-o')+1]=str(dest/'own-rt-iq3')
  replacements=0
  for i,arg in enumerate(link):
   if not arg.endswith('.o'):continue
   if arg==str(BASE/'build'/mode/'entry-main.o'):link[i]=str(dest/'entry-main.o');replacements+=1
   elif arg.endswith('-p49d_submit.cpp.o'):link[i]=str(dest/'p49d_submit.o');replacements+=1
   else:
    src=Path(arg);bind(src);target=dest/'inherited'/(hashlib.sha256(str(src).encode()).hexdigest()[:12]+'-'+src.name);target.parent.mkdir(exist_ok=True)
    os.link(src,target);assert sha(src)==sha(target)
    inherited.append(dict(parent=str(src.relative_to(ROOT)),current=str(target.relative_to(ROOT)),sha256=sha(src)));link[i]=str(target)
  assert replacements==2,(mode,replacements)
  run(link,mode+'-link');artifacts[str((dest/'own-rt-iq3').relative_to(P))]=sha(dest/'own-rt-iq3')
 # Small synthetic production-width draft arithmetic; never uses device backend.
 host=next(r['command'] for r in commands if r['name']=='gnu-host-entry-main');host=host[:host.index('-o')]
 run([*host,'-ffunction-sections','-fdata-sections','-Wl,--gc-sections',P/'p59c_dense_fixture.cpp','-o',B/'draft-fixture'],'draft-fixture-compile')
 artifacts['build/draft-fixture']=sha(B/'draft-fixture')
 for f in (local/'entry-main.cpp',P/'build_engine.py',P/'parent-source-manifest.json',P/'pipeline.py',P/'p59_fixture.cpp',P/'p59c_dense_fixture.cpp',P/'kernel_gate.py',P/'math_gate.py',P/'kernel_overlay.py',P/'submission_overlay.py',P/'kernel_guard.hpp',P/'rope.bf16',P/'mtp-manifest.tsv'):bind(f)
 save(P/'engine-commands.json',commands);bind(P/'engine-commands.json')
 save(P/'evidence/object-identity.json',dict(passed=True,objects=inherited,rebuilt=['entry-main.o','p49d_submit.o']))
 bind(P/'evidence/object-identity.json')
 size=sum(f.stat().st_size for f in B.rglob('*') if f.is_file());assert size<400_000_000
 save(P/'build-device-receipt.json',dict(schema='packet70.cpu-build.v1',passed=True,device_executed=False,sources=sources,artifacts=artifacts,build_logical_bytes=size,nice=19,cpu_affinity=sorted(os.sched_getaffinity(0))))
 print('CPU build complete; no GPU execution; bytes',size,flush=True)
if __name__=='__main__':main()
