"""CPU-only serial incremental build; arithmetic objects reused by exact hash."""
import hashlib,json,os,resource,shutil,subprocess
from pathlib import Path
from compile_turn import turn
P=Path(__file__).resolve().parent;ROOT=P.parents[3];B=P/'build';BASE=P.with_name('packet124c-record-bundle')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert shutil.disk_usage('/').free>=25_000_000_000
 assert sum(f.stat().st_size for f in P.rglob('*') if f.is_file() and 'build' in f.parts and not f.is_symlink())<=300_000_000

def main():
 limits();(B/'tmp').mkdir(exist_ok=True);os.environ['TMPDIR']=str(B/'tmp')
 from kernel_gate import mirror
 from math_gate import closure,check
 check();mapping=mirror();sources={str(f.relative_to(ROOT)):sha(f) for f in closure()}
 sources.update({str(mapping[f].relative_to(ROOT)):sha(mapping[f]) for f in closure()})
 prior=json.loads((BASE/'engine-commands.json').read_text());commands=[];artifacts={};objects=[]
 entry=B/'entry-main.cpp';entry.write_text('#define main packet26_model_entry\n#include '+json.dumps(str(mapping[P/'main.cpp']))+'\n#undef main\n')
 def run(cmd,name):
  cmd=list(map(str,cmd));commands.append(dict(name=name,command=cmd,cwd=str(ROOT)))
  with turn(),(B/(name+'.log')).open('w') as f:subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=1200)
  print(name,'PASS',flush=True)
 for mode in ('gnu-host','device'):
  dest=B/mode;dest.mkdir(exist_ok=True)
  args=next(r['command'] for r in prior if r['name']==mode+'-entry-main');args=args[:args.index('-o')]
  args=[x.replace(str(BASE),str(P)) if x.startswith('-I') else x for x in args]
  run([*args,'-o',dest/'entry-main.o','-c',entry],mode+'-entry-main')
  link=list(next(r['command'] for r in prior if r['name']==mode+'-link'));link[link.index('-o')+1]=str(dest/'own-rt-iq3');replaced=0
  for i,arg in enumerate(link):
   if not arg.endswith('.o'):continue
   if Path(arg).name=='entry-main.o':link[i]=str(dest/'entry-main.o');replaced+=1;continue
   src=Path(arg);assert src.is_file(),src
   target=dest/'inherited'/(hashlib.sha256(arg.encode()).hexdigest()[:12]+'-'+src.name);target.parent.mkdir(exist_ok=True)
   if not target.exists():target.symlink_to(src.resolve())
   sources[str(src.relative_to(ROOT))]=sha(src);objects.append(dict(source=str(src.relative_to(ROOT)),sha256=sha(src)));link[i]=str(target)
  assert replaced==1
  run(link,mode+'-link');artifacts[str((dest/'own-rt-iq3').relative_to(P))]=sha(dest/'own-rt-iq3')
 save(P/'engine-commands.json',commands);save(P/'evidence/object-identity.json',dict(passed=True,objects=objects,device_executed=False))
 for f in (P/'build_engine.py',P/'engine-commands.json',P/'parent-manifest.json',P/'compile_turn.py',P/'kernel_gate.py',P/'kernel_overlay.py',P/'submission_overlay.py',P/'rope.bf16',P/'mtp-manifest.tsv',entry):sources[str(f.relative_to(ROOT))]=sha(f)
 limits();save(P/'build-device-receipt.json',dict(passed=True,device_executed=False,sources=sources,artifacts=artifacts,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));main()
