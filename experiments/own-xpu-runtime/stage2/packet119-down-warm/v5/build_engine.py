"""CPU-only incremental build over frozen packet118, serial compilation."""
import hashlib,importlib.util,json,os,resource,shutil,subprocess,time,sys
from pathlib import Path
P=Path(__file__).resolve().parent; ROOT=P.parents[4]; STAGE=P.parents[1]
BASE=STAGE/'packet118-record-bundle'; LOCAL=P.parent; B=P/'build'
CHECKED=LOCAL/'build/checked'/LOCAL.relative_to(ROOT)
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def save(path,row):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(row,indent=2)+'\n')
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 assert shutil.disk_usage('/').free>=25_000_000_000
 assert sum(f.stat().st_size for f in LOCAL.rglob('*') if f.is_file() and 'build' in f.parts and not f.is_symlink())<=250_000_000
def compiler_turn():
 path=STAGE/'packet94-hc-norm-fusion/compile_turn.py'
 spec=importlib.util.spec_from_file_location('p119_compile_turn',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 return m.turn()
def run(cmd,name):
 limits(); B.mkdir(exist_ok=True);started=time.monotonic()
 with compiler_turn(),(B/(name+'.log')).open('w') as log:
  subprocess.run(list(map(str,cmd)),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1200)
 print(name,'PASS',flush=True)
 return dict(name=name,command=list(map(str,cmd)),seconds=time.monotonic()-started)
def main():
 limits();B.mkdir(exist_ok=True)
 from prepare_sources import prepare
 prepare()
 prior=json.loads((BASE/'engine-commands.json').read_text());commands=[];sources={};artifacts={}
 # Pin every native source and object actually inherited from packet118.
 parent=json.loads((BASE/'build-device-receipt.json').read_text())
 for name,digest in parent['sources'].items():
  path=ROOT/name
  if path.suffix not in ('.cpp','.hpp','.inc','.o','.bf16','.tsv'):continue
  assert sha(path)==digest,'frozen parent source changed: '+name
  sources[name]=digest
 for mode in ('gnu-host','device'):
  dest=B/mode;dest.mkdir(exist_ok=True)
  args=next(r['command'] for r in prior if r['name']==mode+'-entry-main');args=args[:args.index('-o')]
  args=[x for x in args if not x.startswith('-I')]+['-I'+str(CHECKED),'-I'+str(LOCAL)]
  stems=('entry-main','p49d_submit','p49d_expert_submit')
  for stem in stems:
   src=P/'native-src/entry-main.cpp' if stem=='entry-main' else CHECKED/(stem+'.cpp')
   commands.append(run([*args,'-o',dest/(stem+'.o'),'-c',src],mode+'-'+stem))
  link=list(next(r['command'] for r in prior if r['name']==mode+'-link'));link[link.index('-o')+1]=str(dest/'own-rt-iq3')
  replaced=[]
  for i,arg in enumerate(link):
   if not arg.endswith('.o'):continue
   stem=next((s for s in stems if Path(arg).name in (s+'.o',s+'.cpp.o') or Path(arg).name.endswith(('-'+s+'.o','-'+s+'.cpp.o'))),None)
   if stem:link[i]=str(dest/(stem+'.o'));replaced.append(stem)
   else:sources[str(Path(arg).relative_to(ROOT))]=sha(arg)
  assert sorted(replaced)==sorted(stems),(replaced,stems)
  commands.append(run(link,mode+'-link'));artifacts[str((dest/'own-rt-iq3').relative_to(P))]=sha(dest/'own-rt-iq3')
 for f in [*P.glob('native/*'),*P.glob('native-src/*'),*LOCAL.glob('*.hpp'),*LOCAL.glob('*.cpp'),*LOCAL.joinpath('build/checked').rglob('*'),P/'prepare_sources.py',P/'build_engine.py',P/'source-copy-provenance.json']:
  if f.is_file():sources[str(f.relative_to(ROOT))]=sha(f)
 sources.update(json.loads((P/'source-copy-provenance.json').read_text())['sources'])
 save(P/'engine-commands.json',commands)
 save(P/'evidence/build.json',dict(passed=True,device_executed=False,sources=sources,artifacts=artifacts,commands=commands,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
 limits()
if __name__=='__main__':main()
