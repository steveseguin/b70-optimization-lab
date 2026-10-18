"""Packet105 incremental build from frozen packet97e; no mutable parent pins."""
import hashlib,json,os,resource,subprocess
from pathlib import Path
from compile_turn import turn
P=Path(__file__).resolve().parent;ROOT=P.parents[3];B=P/'build';BASE=P.parent/'packet105-head-split'
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
def check_map(root,rows):
 for n,h in rows.items():assert sha(root/n)==h,n
def provenance():
 r=json.loads((P/'build-device-receipt.json').read_text());check_map(ROOT,r['sources']);check_map(P,r['artifacts']);return r
def main():
 limits();(B/'tmp').mkdir(exist_ok=True);os.environ['TMPDIR']=str(B/'tmp')
 (B/'fusion-rope.hpp').write_bytes((BASE/'build/fusion-rope.hpp').read_bytes())
 from kernel_gate import mirror
 from math_gate import closure,check
 check();mapping=mirror()
 sources={str(f.relative_to(ROOT)):sha(f) for f in closure()}
 sources.update({str(mapping[f].relative_to(ROOT)):sha(mapping[f]) for f in closure()})
 parent=json.loads((P/'parent-build-receipt.json').read_text())
 # Inherited object identity and its frozen source closure. Deliberately omit
 # parent preparation receipts, selection, evidence and orchestration outputs.
 for n,h in parent['sources'].items():
  if Path(n).suffix in ('.cpp','.hpp','.inc','.o','.bf16','.tsv'):
   assert sha(ROOT/n)==h,n;sources[n]=h
 prior=json.loads((P/'parent-engine-commands.json').read_text());commands=[];artifacts={};objects=[]
 entry=B/'entry-main.cpp';entry.write_text('#define main packet26_model_entry\n#include '+json.dumps(str(mapping[P/'main.cpp']))+'\n#undef main\n')
 def run(cmd,name):
  cmd=list(map(str,cmd));commands.append(dict(name=name,command=cmd,cwd=str(ROOT)))
  with turn(),(B/(name+'.log')).open('w') as f:subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=1200)
  print(name,'PASS',flush=True)
 for mode in ('gnu-host','device'):
  dest=B/mode;dest.mkdir(exist_ok=True)
  args=next(r['command'] for r in prior if r['name']==mode+'-entry-main');args=args[:args.index('-o')]
  args=[x.replace(str(BASE),str(P)) if x.startswith('-I') else x for x in args]
  rebuilt=['entry-main']
  for stem in rebuilt:run([*args,'-o',dest/(stem+'.o'),'-c',entry if stem=='entry-main' else mapping[P/(stem+'.cpp')]],mode+'-'+stem)
  link=list(next(r['command'] for r in prior if r['name']==mode+'-link'));link[link.index('-o')+1]=str(dest/'own-rt-iq3');replaced=[]
  for i,arg in enumerate(link):
   if not arg.endswith('.o'):continue
   stem=next((s for s in rebuilt if Path(arg).name in (s+'.o',s+'.cpp.o') or Path(arg).name.endswith('-'+s+'.cpp.o') or Path(arg).name.endswith('-'+s+'.o')),None)
   if stem:link[i]=str(dest/(stem+'.o'));replaced.append(stem)
   else:
    src=Path(arg);target=dest/'inherited'/(hashlib.sha256(arg.encode()).hexdigest()[:12]+'-'+src.name);target.parent.mkdir(exist_ok=True)
    if not target.exists():os.link(src,target)
    assert sha(src)==sha(target);sources[str(src.relative_to(ROOT))]=sha(src);sources[str(target.relative_to(ROOT))]=sha(target)
    objects.append(dict(source=str(src.relative_to(ROOT)),local=str(target.relative_to(ROOT)),sha256=sha(src)));link[i]=str(target)
  for stem in set(rebuilt)-set(replaced):link.insert(link.index('-o'),str(dest/(stem+'.o')));replaced.append(stem)
  assert sorted(replaced)==sorted(rebuilt)
  run(link,mode+'-link');artifacts[str((dest/'own-rt-iq3').relative_to(P))]=sha(dest/'own-rt-iq3')
 save(P/'engine-commands.json',commands);save(P/'evidence/object-identity.json',dict(passed=True,device_executed=False,objects=objects))
 for f in (P/'compile_turn.py',P/'build_engine.py',P/'engine-commands.json',P/'evidence/object-identity.json',P/'kernel_guard.hpp',P/'kernel_gate.py',P/'math_gate.py',P/'kernel_overlay.py',P/'submission_overlay.py',P/'rope.bf16',P/'mtp-manifest.tsv',entry):sources[str(f.relative_to(ROOT))]=sha(f)
 size=sum(f.stat().st_size for f in B.rglob('*') if f.is_file() and not f.is_symlink());assert size<=250_000_000,size
 save(P/'build-device-receipt.json',dict(schema='packet105.cpu-build.v1',passed=True,device_executed=False,sources=sources,artifacts=artifacts,build_logical_bytes=size,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
 print('sealed build receipt; logical bytes',size,flush=True)
if __name__=='__main__':main()
