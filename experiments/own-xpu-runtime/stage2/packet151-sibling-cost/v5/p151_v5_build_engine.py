"""Packet142 local incremental build; compiler turns always use the ops arbiter."""
import hashlib,importlib.util,json,os,resource,shutil,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent;LOCAL=P.parent;ROOT=P.parents[4];STAGE=P.parents[1];BASE=LOCAL;B=P/'build'
CHECKED=LOCAL/'build/checked'/LOCAL.relative_to(ROOT)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def save(p,row):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(row,indent=2)+'\n')
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert shutil.disk_usage('/').free>=30_000_000_000
 size=sum(f.stat().st_size for f in LOCAL.rglob('*') if f.is_file() and not f.is_symlink() and 'build' in f.parts and not f.is_relative_to(P/'evidence'))
 assert size<=300_000_000,size
 return size
def compiler_turn():
 import sys
 if str(LOCAL) not in sys.path:sys.path.append(str(LOCAL))
 spec=importlib.util.spec_from_file_location('ops_compile_turn',STAGE.parent/'ops/compile_turn.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m.turn()
def run(cmd,name):
 limits();t=time.monotonic()
 with compiler_turn(),(B/(name+'.log')).open('w') as log:subprocess.run(list(map(str,cmd)),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1200)
 print(name,'PASS',flush=True);return dict(name=name,command=list(map(str,cmd)),seconds=time.monotonic()-t)
def main():
 limits();(LOCAL/'build').mkdir(exist_ok=True)
 if not (LOCAL/'build/checked').exists():(LOCAL/'build/checked').symlink_to('../native-base',target_is_directory=True)
 pinned=json.loads((LOCAL/'immutable-binaries.json').read_text())
 prior=json.loads((LOCAL/'lineage-inputs/packet136-history/engine-commands.json').read_text());commands=[];artifacts={};inherited={}
 for mode in ('gnu-host','device'):
  dest=B/mode;dest.mkdir(exist_ok=True)
  args=list(next(r['command'] for r in prior if r['name']==mode+'-entry-main'));args=args[:args.index('-o')]
  args=[v for v in args if not v.startswith(('-I','-O'))]+['-O2','-I'+str(CHECKED),'-I'+str(LOCAL)]
  for stem in ('entry-main','p49d_submit'):
   src=P/'native-src/entry-main.cpp' if stem=='entry-main' else CHECKED/'p49d_submit.cpp'
   cmd=[*args,'-c',src,'-o',dest/(stem+'.o')]
   commands.append(run(cmd,mode+'-'+stem))
  link=list(next(r['command'] for r in prior if r['name']==mode+'-link'));link[link.index('-o')+1]=str(dest/'own-rt-iq3')
  for i,arg in enumerate(link):
   if not arg.endswith('.o'):continue
   stem=next((s for s in ('entry-main','p49d_submit') if Path(arg).name.endswith((s+'.o',s+'.cpp.o'))),None)
   if stem:link[i]=str(dest/(stem+'.o'))
   else:
    src=Path(arg);assert sha(src)==pinned[str(src.resolve())],'frozen parent object changed: '+str(src)
    target=dest/'inherited'/src.name;target.parent.mkdir(exist_ok=True)
    if not target.exists():target.symlink_to(src.resolve())
    assert sha(src)==sha(target);inherited[str(src.resolve().relative_to(ROOT))]=sha(target);link[i]=str(target)
  commands.append(run(link,mode+'-link'));artifacts[str((dest/'own-rt-iq3').relative_to(ROOT))]=sha(dest/'own-rt-iq3')
  save(P/'engine-commands.json',commands)
 sources={str(f.relative_to(ROOT)):sha(f) for f in [*[P/'native'/n for n in ('engine_bracket.hpp','draft_bracket.hpp','bracket_boundary.hpp','probe_exchange.hpp')],*P.glob('native-src/*'),*LOCAL.joinpath('native-base').rglob('*'),P/'p151_v5_build_engine.py'] if f.is_file()}
 sources.update(inherited)
 save(P/'evidence/build.json',dict(passed=True,device_executed=False,sources=sources,artifacts=artifacts,commands=commands,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,build_bytes=limits()))
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
