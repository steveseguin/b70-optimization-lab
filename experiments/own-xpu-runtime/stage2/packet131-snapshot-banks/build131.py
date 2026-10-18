"""CPU-only packet131 incremental build; frozen packet124c objects are inputs."""
import hashlib, importlib.util, json, os, resource, shutil, subprocess, sys, time
from pathlib import Path
P=Path(__file__).resolve().parent; ROOT=P.parents[3]; B=P/'build'
BASE=P.with_name('packet124c-record-bundle')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def save(p,v):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert shutil.disk_usage('/').free>=25_000_000_000,'root below 25 GB'
 assert sum(f.stat().st_size for f in B.rglob('*') if f.is_file() and not f.is_symlink())<=300_000_000,'build exceeds 300 MB'
def cpu_main():
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));limits()
 os.environ.update(OMP_NUM_THREADS='2',TMPDIR=str(B/'tmp'))
def turn():
 # The exact packet94 lock, including the coordinator reservation check.
 spec=importlib.util.spec_from_file_location('p131_compile_turn',P.with_name('packet94-hc-norm-fusion')/'compile_turn.py')
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m.turn()
def run(cmd,name):
 limits();cmd=list(map(str,cmd));start=time.monotonic()
 with turn(),(B/(name+'.log')).open('w') as log:
  limits()  # Recheck after a coordinator/foreign compiler wait.
  subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1200)
 print(name,'PASS',flush=True);limits()
 return dict(name=name,command=cmd,seconds=time.monotonic()-start)
def main():
 from kernel_gate import mirror
 from math_gate import check,closure
 check();mapping=mirror()
 entry=B/'entry-main.cpp';entry.write_text('#define main packet26_model_entry\n#include '+json.dumps(str(mapping[P/'main.cpp']))+'\n#undef main\n')
 prior=json.loads((BASE/'engine-commands.json').read_text());commands=[];sources={};artifacts={}
 for f in closure():sources[str(f.relative_to(ROOT))]=sha(f)
 # Native bytes and objects inherited from the frozen build remain hash bound.
 for name,h in json.loads((BASE/'build-device-receipt.json').read_text())['sources'].items():
  f=ROOT/name
  if f.suffix in ('.cpp','.hpp','.inc','.o','.bf16','.tsv'):
   assert sha(f)==h,name;sources[name]=h
 for mode in ('gnu-host','device'):
  dest=B/mode;dest.mkdir(exist_ok=True)
  args=next(r['command'] for r in prior if r['name']==mode+'-entry-main');args=args[:args.index('-o')]
  args=[x for x in args if not x.startswith('-I')]+['-I'+str(B/'checked'/P.relative_to(ROOT)),'-I'+str(P)]
  for stem in ('entry-main','p49d_submit'):
   commands.append(run([*args,'-c',entry if stem=='entry-main' else mapping[P/(stem+'.cpp')],'-o',dest/(stem+'.o')],mode+'-'+stem))
  link=list(next(r['command'] for r in prior if r['name']==mode+'-link'));link[link.index('-o')+1]=str(dest/'own-rt-iq3');replaced=[]
  for i,arg in enumerate(link):
   if not arg.endswith('.o'):continue
   stem=next((s for s in ('entry-main','p49d_submit') if Path(arg).name in (s+'.o',s+'.cpp.o') or Path(arg).name.endswith(('-'+s+'.o','-'+s+'.cpp.o'))),None)
   if stem:link[i]=str(dest/(stem+'.o'));replaced.append(stem)
   else:sources[str(Path(arg).relative_to(ROOT))]=sha(arg)
  assert sorted(replaced)==['entry-main','p49d_submit'],replaced
  commands.append(run(link,mode+'-link'));artifacts[str((dest/'own-rt-iq3').relative_to(P))]=sha(dest/'own-rt-iq3')
 for f in [entry,P/'build131.py',P/'copy131.json',*mapping.values()]:sources[str(f.relative_to(ROOT))]=sha(f)
 save(P/'engine-commands.json',commands)
 save(P/'build-device-receipt.json',dict(schema='packet131.cpu-build.v1',passed=True,device_executed=False,sources=sources,artifacts=artifacts,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
if __name__=='__main__':cpu_main();main()
