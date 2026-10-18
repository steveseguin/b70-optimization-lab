#!/usr/bin/env python3
"""Build the combined engine; reuse hash-bound packet60 unchanged objects."""
import hashlib,json,os,shlex,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];B=P/'build'
BASE=P.parent/'packet61-spin-hcfusion';HC=P.parent/'packet60-hc-fusion';PARENT=P.parent/'packet56-draft-prefix'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert os.environ.get('OMP_NUM_THREADS')=='2'
 assert not (P/'screen-seal.json').exists()
 (B/'tmp').mkdir(parents=True,exist_ok=True)
 if not (B/'fusion-rope.hpp').exists():os.link(BASE/'build/fusion-rope.hpp',B/'fusion-rope.hpp')
 os.environ['TMPDIR']=str(B/'tmp')
 commands=[];sources={};artifacts={}
 def bind(path):sources[str(path.relative_to(ROOT))]=sha(path)
 def run(cmd,name):
  cmd=list(map(str,cmd));commands.append(dict(command=cmd,cwd=str(ROOT),name=name))
  with (B/(name+'.log')).open('w') as log:subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
  print(name,'PASS',flush=True)
 # Every fused kernel and integration body comes directly from sealed packet60.
 for name in ('p60_submit.cpp','p60_submit.hpp','p60_math.hpp','p60_kernels.hpp','fixture.cpp','integrated_fixture.cpp'):
  assert sha(P/name)==sha(HC/name),name
 parent_receipt=json.loads((HC/'build-device-receipt.json').read_text())
 for name,digest in parent_receipt['sources'].items():assert sha(ROOT/name)==digest,name
 sources.update(parent_receipt['sources']);bind(HC/'build-device-receipt.json')
 base_receipt=json.loads((BASE/'build-device-receipt.json').read_text())
 for name,digest in base_receipt['sources'].items():assert sha(ROOT/name)==digest,name
 sources.update(base_receipt['sources']);bind(BASE/'build-device-receipt.json')
 from kernel_gate import mirror
 from math_gate import closure
 mapping=mirror()
 for path in closure():bind(path);bind(mapping[path])
 prior=json.loads((BASE/'engine-commands.json').read_text())
 LOCAL=B/'engine';LOCAL.mkdir(exist_ok=True)
 # cpu_gate's integration fixture includes exactly the combined checked engine.
 (LOCAL/'main.cpp').write_text('#include '+json.dumps(str(mapping[P/'main.cpp']))+'\n')
 (LOCAL/'entry-main.cpp').write_text('#define main packet26_model_entry\n#include "main.cpp"\n#undef main\n')
 for mode in ('gnu-host','device'):
  dest=B/mode;dest.mkdir(exist_ok=True)
  base=next(x['command'] for x in prior if x['name']==mode+'-entry-main')
  base=base[:base.index('-o')]
  base=[x.replace(str(BASE),str(P)) if x.startswith('-I') else x for x in base]
  run([*base,'-o',dest/'entry-main.o','-c',LOCAL/'entry-main.cpp'],mode+'-entry-main')
  if mode=='device':run([*base,'-o',dest/'single_device.o','-c',mapping[P/'single_device.cpp']],mode+'-single_device')
  run(['g++','-std=c++20','-O2','-DP56X_SLEEP20=0','-c',P/'host_wait_mode.cpp','-o',dest/'host_wait_mode.o'],mode+'-wait-policy')
  link=list(next(x['command'] for x in prior if x['name']==mode+'-link'))
  link[link.index('-o')+1]=str(dest/'own-rt-iq3')
  for i,arg in enumerate(link):
   if not arg.endswith('.o'):continue
   if arg==str(BASE/'build'/mode/'entry-main.o'):link[i]=str(dest/'entry-main.o')
   elif mode=='device' and arg==str(BASE/'build'/mode/'single_device.o'):link[i]=str(dest/'single_device.o')
   else:
    src=Path(arg);bind(src)
    target=dest/'inherited'/(hashlib.sha256(str(src).encode()).hexdigest()[:12]+'-'+src.name);target.parent.mkdir(exist_ok=True)
    if not target.exists():os.link(src,target)
    assert sha(target)==sha(src)
    link[i]=str(target)
  link.append(str(dest/'host_wait_mode.o'))
  run(link,mode+'-link');artifacts[str((dest/'own-rt-iq3').relative_to(P))]=sha(dest/'own-rt-iq3')
 for stem in ('native_controller_test','native_mailbox_fault_test','host_wait_test'):
  run(['g++','-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-pthread','-DP56X_SLEEP20=0',P/'host_wait_mode.cpp',P/(stem+'.cpp'),'-o',B/stem],stem+'-build')
  bind(P/(stem+'.cpp'));artifacts['build/'+stem]=sha(B/stem)
 for path in LOCAL.iterdir():bind(path)
 for leaf in ('build_engine.py','build.py','kernel_gate.py','kernel_overlay.py','submission_overlay.py','math_gate.py','kernel_guard.hpp','host_spin.hpp','host_wait_mode.cpp','host_wait_test.cpp','mtp-manifest.tsv','rope.bf16','wait-option.json','primitive-build-receipt.json'):bind(P/leaf)
 save(P/'engine-commands.json',commands);bind(P/'engine-commands.json')
 sealed={};external={}
 for name,digest in sources.items():
  original=ROOT/name;assert sha(original)==digest,name
  if original.resolve().is_relative_to(ROOT):sealed[name]=digest
  else:
   snapshot=P/'evidence/inherited-build-inputs'/name;snapshot.parent.mkdir(parents=True,exist_ok=True)
   if not snapshot.exists():os.link(original,snapshot)
   assert sha(snapshot)==digest
   relative=str(snapshot.relative_to(ROOT));sealed[relative]=digest
   external[name]=dict(snapshot=relative,sha256=digest)
 save(P/'build-device-receipt.json',dict(schema='packet61x.lean-build.v1',passed=True,device_executed=False,
  sources=sealed,artifacts=artifacts,external_compiler_inputs=external,
  unchanged_objects='Hardlinks to sealed packet61 compiler outputs; new host entry/device wait and fixed spin policy',
  nice=19,cpu_affinity=sorted(os.sched_getaffinity(0))))
 print('Combined engine built; no device execution',flush=True)
if __name__=='__main__':main()
