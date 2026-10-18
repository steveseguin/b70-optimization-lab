"""Serial incremental CPU/SYCL compilation; never executes a device program."""
import hashlib,importlib.util,json,os,resource,shutil,subprocess,time
from pathlib import Path
from native_source import P,ROOT,BASE,CHECKED,generate
B=P/'build'
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def save(path,row):
 Path(path).parent.mkdir(parents=True,exist_ok=True);Path(path).write_text(json.dumps(row,indent=2)+'\n')
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 assert shutil.disk_usage(P).free>=12_000_000_000
 assert sum(f.stat().st_size for f in B.rglob('*') if f.is_file())<=300_000_000
def compiler_turn():
 path=P.parent/'packet94-hc-norm-fusion/compile_turn.py'
 spec=importlib.util.spec_from_file_location('packet94_compile_turn',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 return m.turn()
def run(cmd,name):
 limits();start=time.monotonic()
 with compiler_turn(),(B/(name+'.log')).open('w') as log:
  subprocess.run(list(map(str,cmd)),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1200)
 print(name,'PASS',flush=True)
 return dict(name=name,command=list(map(str,cmd)),seconds=time.monotonic()-start)
def main():
 limits();native=generate();prior=json.loads((BASE/'engine-commands.json').read_text());commands=[];sources={};artifacts={}
 save(P/'lineage/parent-engine-commands.json',prior)
 for mode in ('gnu-host','device'):
  dest=B/mode;dest.mkdir(exist_ok=True)
  args=next(r['command'] for r in prior if r['name']==mode+'-entry-main');args=args[:args.index('-o')]
  args=[a for a in args if not a.startswith('-I')]+['-I'+str(CHECKED),'-I'+str(P)]
  for stem,src in [('entry-main',native/'entry-main.cpp'),('p49d_submit',CHECKED/'p49d_submit.cpp')]:
   commands.append(run([*args,'-o',dest/(stem+'.o'),'-c',src],mode+'-'+stem))
  link=list(next(r['command'] for r in prior if r['name']==mode+'-link'));link[link.index('-o')+1]=str(dest/'own-rt-iq3')
  for i,arg in enumerate(link):
   if not arg.endswith('.o'):continue
   if Path(arg).name in ('entry-main.o','p49d_submit.o'):link[i]=str(dest/Path(arg).name)
   else:sources[str(Path(arg).relative_to(ROOT))]=sha(arg)
  commands.append(run(link,mode+'-link'));artifacts[str((dest/'own-rt-iq3').relative_to(P))]=sha(dest/'own-rt-iq3')
 for f in [*(P/'sources').rglob('*'),*P.glob('p109*.hpp'),P/'engine_fusion.hpp',P/'source-copy-provenance.json',P/'native_source.py',P/'build_engine.py',*P.glob('native/*'),*native.glob('*'),P/'lineage/parent-engine-commands.json']:
  if f.is_file():sources[str(f.relative_to(ROOT))]=sha(f)
 for f in (BASE/'kernel_guard.hpp',P.parent/'packet94-hc-norm-fusion/compile_turn.py'):sources[str(f.relative_to(ROOT))]=sha(f)
 limits();save(P/'engine-commands.json',commands)
 save(P/'evidence/build.json',dict(passed=True,device_executed=False,sources=sources,artifacts=artifacts,commands=commands,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
if __name__=='__main__':main()
