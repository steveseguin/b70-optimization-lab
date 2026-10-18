"""Serial incremental build using packet70's actual packet65 object provenance."""
import hashlib,json,os,resource,subprocess
from compile_turn import turn
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];B=P/'build';BASE=P.parent/'packet97-record-bundle'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
def main():
 limits();assert not (P/'build-device-receipt.json').exists()
 (B/'tmp').mkdir(exist_ok=True);os.environ['TMPDIR']=str(B/'tmp')
 if not (B/'fusion-rope.hpp').exists():os.link(BASE/'build/fusion-rope.hpp',B/'fusion-rope.hpp')
 parent=json.loads((BASE/'build-device-receipt.json').read_text());sources=dict(parent['sources']);artifacts={};commands=[];objects=[]
 for n,h in sources.items():assert sha(ROOT/n)==h,n
 # Packet70 intentionally reuses packet65. Its copied engine-commands.json
 # predates that reuse, so use the actual packet65 link receipt, never the stale one.
 for n,h in json.loads((P/'parent-source-manifest.json').read_text()).items():assert sha(ROOT/n)==h,n
 from kernel_gate import mirror
 from math_gate import closure,check
 check();mapping=mirror()
 for f in closure():sources[str(f.relative_to(ROOT))]=sha(f);sources[str(mapping[f].relative_to(ROOT))]=sha(mapping[f])
 entry=B/'entry-main.cpp';entry.write_text('#define main packet26_model_entry\n#include '+json.dumps(str(mapping[P/'main.cpp']))+'\n#undef main\n')
 prior=json.loads((BASE/'engine-commands.json').read_text())
 def run(cmd,name):
  cmd=list(map(str,cmd));commands.append(dict(name=name,command=cmd,cwd=str(ROOT)))
  with turn(), (B/(name+'.log')).open('w') as f:subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=1200)
  print(name,'PASS',flush=True)
 for mode in ('gnu-host','device'):
  dest=B/mode;dest.mkdir(exist_ok=True)
  args=next(r['command'] for r in prior if r['name']==mode+'-entry-main');args=args[:args.index('-o')]
  args=[x.replace(str(BASE),str(P)).replace(str(P.parent/'packet65-expert-occupancy'),str(P)) if x.startswith('-I') else x for x in args]
  rebuilt=('entry-main','p49d_submit','p49d_expert_submit')
  for stem in rebuilt:run([*args,'-o',dest/(stem+'.o'),'-c',entry if stem=='entry-main' else mapping[P/(stem+'.cpp')]],mode+'-'+stem)
  link=list(next(r['command'] for r in prior if r['name']==mode+'-link'));link[link.index('-o')+1]=str(dest/'own-rt-iq3');replaced=[]
  for i,arg in enumerate(link):
   if not arg.endswith('.o'):continue
   stem=next((s for s in rebuilt if Path(arg).name in (s+'.o',s+'.cpp.o') or Path(arg).name.endswith('-'+s+'.cpp.o') or Path(arg).name.endswith('-'+s+'.o')),None)
   if stem:link[i]=str(dest/(stem+'.o'));replaced.append(stem)
   else:
    src=Path(arg);target=dest/'inherited'/(hashlib.sha256(arg.encode()).hexdigest()[:12]+'-'+src.name);target.parent.mkdir(exist_ok=True)
    if not target.exists():os.link(src,target)
    assert sha(src)==sha(target);sources[str(src.relative_to(ROOT))]=sha(src)
    objects.append(dict(source=str(src.relative_to(ROOT)),local=str(target.relative_to(ROOT)),sha256=sha(src)));link[i]=str(target)

  for stem in set(rebuilt)-set(replaced):link.insert(link.index('-o'),str(dest/(stem+'.o')));replaced.append(stem)
  assert sorted(replaced)==sorted(rebuilt),replaced
  run(link,mode+'-link');artifacts[str((dest/'own-rt-iq3').relative_to(P))]=sha(dest/'own-rt-iq3')
 save(P/'engine-commands.json',commands);save(P/'evidence/object-identity.json',dict(passed=True,device_executed=False,objects=objects))
 for f in (P/'compile_turn.py',P/'build_engine.py',P/'engine-commands.json',P/'parent-source-manifest.json',P/'evidence/object-identity.json',P/'kernel_guard.hpp',P/'kernel_gate.py',P/'math_gate.py',P/'kernel_overlay.py',P/'submission_overlay.py',P/'rope.bf16',P/'mtp-manifest.tsv',entry):sources[str(f.relative_to(ROOT))]=sha(f)
 size=sum(f.stat().st_size for f in B.rglob('*') if f.is_file());assert size<500_000_000,size
 save(P/'build-device-receipt.json',dict(schema='packet97.cpu-build.v1',passed=True,device_executed=False,sources=sources,artifacts=artifacts,build_logical_bytes=size,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
 print('sealed build receipt; logical bytes',size,flush=True)
PARENTS={'rec-parallel':P,'rec-both-plus':P}
def provenance():
 from chain_seal import check_map
 row=json.loads((P/'build-device-receipt.json').read_text());assert row['passed'] and not row['device_executed']
 check_map(ROOT,row['sources']);check_map(P,row['artifacts'])
 bins={m:dict(path=str((P/'build'/m/'own-rt-iq3').relative_to(ROOT)),sha256=row['artifacts']['build/'+m+'/own-rt-iq3']) for m in ('device','gnu-host')}
 return dict(row,variants={k:dict(binaries=bins) for k in PARENTS})
def activate(recurrence):
 assert recurrence in PARENTS
 provenance() # one binary, runtime selection only
if __name__=='__main__':main()
