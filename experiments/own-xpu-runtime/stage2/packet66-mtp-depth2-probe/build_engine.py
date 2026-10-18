#!/usr/bin/env python3
"""Serial host-only rebuild of entry objects; reuse unchanged packet61x kernels."""
import hashlib,json,os,resource,shutil,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];B=P/'build'
BASE=P.with_name('packet61x-spin-hcfusion-wait')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert os.environ.get('OMP_NUM_THREADS')=='2'
 assert not (P/'screen-seal.json').exists()
 assert shutil.disk_usage(ROOT).free>=10*1024**3
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
  cmd=list(map(str,cmd));commands.append(dict(command=cmd,cwd=str(ROOT),name=name))
  with (B/(name+'.log')).open('w') as log:subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,stdin=subprocess.DEVNULL)
  print(name,'PASS',flush=True)
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
 cmd=next(x['command'] for x in commands if x['name']=='gnu-host-entry-main');cmd=cmd[:cmd.index('-o')]
 fixture=(P/'probe_fixture.cpp').read_text().replace('#include "main.cpp"','#include '+json.dumps(str(local/'main.cpp')))
 (local/'probe_fixture.cpp').write_text(fixture)
 run([*cmd,'-o',B/'probe_fixture.o','-c',local/'probe_fixture.cpp'],'fixture-compile')
 link=list(next(x['command'] for x in commands if x['name']=='gnu-host-link'))
 link=[x for x in link if not x.endswith('own-rt-iq3-entry.cpp.o')]
 link=[str(B/'probe_fixture.o') if x==str(B/'gnu-host/entry-main.o') else x for x in link];link[link.index('-o')+1]=str(B/'probe-fixture')
 run(link,'fixture-link');artifacts['build/probe-fixture']=sha(B/'probe-fixture')
 # Compile the SAME small driver against the original depth-1 implementation.
 # Only add fixture observation accessors; its compute/begin/poll bodies stay original.
 original=BASE/'mtp.hpp';bind(original)
 api=(P/'mtp.hpp').read_text().split('// Fixture switch only;',1)[1].split(' void set_reverse_hidden',1)[0]
 reference=original.read_text().replace('public:\n','public:\n // Fixture switch only;'+api,1)
 reference=reference.replace(' void set_reverse_hidden',' void flush_probe() {}\n void set_reverse_hidden',1)
 for name in ('mtp_kernels.hpp','p56_prefix.hpp'):
  reference=reference.replace('#include "'+name+'"','#include '+json.dumps(str(mapping[P/name])))
 (local/'reference-mtp.hpp').write_text(reference)
 refmain=mapping[P/'main.cpp'].read_text().replace(str(mapping[P/'mtp.hpp']),str(local/'reference-mtp.hpp'))
 (local/'reference-main.cpp').write_text(refmain)
 refdriver=(P/'probe_fixture.cpp').read_text().replace('#include "main.cpp"','#include '+json.dumps(str(local/'reference-main.cpp')))
 (local/'reference-fixture.cpp').write_text(refdriver)
 run([*cmd,'-o',B/'reference-fixture.o','-c',local/'reference-fixture.cpp'],'reference-fixture-compile')
 reflink=[str(B/'reference-fixture.o') if x==str(B/'probe_fixture.o') else x for x in link];reflink[reflink.index('-o')+1]=str(B/'reference-fixture')
 run(reflink,'reference-fixture-link');artifacts['build/reference-fixture']=sha(B/'reference-fixture')
 data=(P/'fixture.cpp').read_text().replace('#include "p60_math.hpp"','#include '+json.dumps(str(mapping[P/'p60_math.hpp'])))
 (local/'fixture-data.cpp').write_text(data)
 target=(P/'integrated_fixture.cpp').read_text().replace('#include "main.cpp"','#include '+json.dumps(str(local/'main.cpp'))).replace('#include "fixture.cpp"','#include '+json.dumps(str(local/'fixture-data.cpp')))
 (local/'target-fixture.cpp').write_text(target)
 run([*cmd,'-o',B/'target-fixture.o','-c',local/'target-fixture.cpp'],'target-fixture-compile')
 tlink=[str(B/'target-fixture.o') if x==str(B/'probe_fixture.o') else x for x in link];tlink[tlink.index('-o')+1]=str(B/'target-fixture')
 run(tlink,'target-fixture-link');artifacts['build/target-fixture']=sha(B/'target-fixture')
 for p in local.iterdir():bind(p)
 for name in ('build_engine.py','probe_fixture.cpp','cpu_gate.py','integrated_fixture.cpp','fixture.cpp','kernel_gate.py','kernel_overlay.py','submission_overlay.py','math_gate.py','kernel_guard.hpp','mtp-manifest.tsv','rope.bf16','selection-decision.json','parent-source-manifest.json'):bind(P/name)
 save(P/'engine-commands.json',commands);bind(P/'engine-commands.json')
 size=sum(p.stat().st_size for p in B.rglob('*') if p.is_file());assert size<10**9
 save(P/'build-device-receipt.json',dict(schema='packet66.lean-build.v1',passed=True,device_executed=False,sources=sources,artifacts=artifacts,logical_build_bytes=size,commands=commands,compiler_version=subprocess.check_output(['/opt/intel/oneapi/compiler/latest/bin/icpx','--version'],text=True),max_address_space_bytes=8*1024**3,nice=19,cpu_affinity=sorted(os.sched_getaffinity(0))))
if __name__=='__main__':main()
