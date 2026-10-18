"""Incremental build; commands run under packet94's serial compile lock."""
import hashlib,importlib.util,json,os,resource,shutil,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[4];STAGE=P.parents[1]
BASE=STAGE/'packet103-record-bundle';B=P/'build';CHECKED=BASE/'build/checked'/BASE.relative_to(ROOT)
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
 assert shutil.disk_usage(P).free>=25_000_000_000
 assert sum(f.stat().st_size for f in P.parent.rglob('*') if f.is_file() and 'build' in f.parts)<=250_000_000
def compiler_turn():
 path=STAGE/'packet94-hc-norm-fusion/compile_turn.py'
 spec=importlib.util.spec_from_file_location('p115_compile_turn',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 return m.turn()
def run(cmd,name):
 limits();B.mkdir(exist_ok=True);started=time.monotonic()
 with compiler_turn(),(B/(name+'.log')).open('w') as log:
  subprocess.run(list(map(str,cmd)),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1200)
 return dict(name=name,command=list(map(str,cmd)),seconds=time.monotonic()-started)
def main():
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('--large-image',type=Path,required=True);ap.add_argument('--normal-image',type=Path,required=True)
 a=ap.parse_args();limits();B.mkdir(exist_ok=True)
 prior=json.loads((BASE/'engine-commands.json').read_text());commands=[];sources={};artifacts={}
 mirror_path=P.parent/'mirror.py'
 spec=importlib.util.spec_from_file_location('p115_v5_dispatch_mirror',mirror_path)
 mirror=importlib.util.module_from_spec(spec);spec.loader.exec_module(mirror)
 checked_dispatch=mirror.prepare(P.parent/'expert_dispatch.cpp')
 # Close over every checked header and inherited object provenance, not just
 # the four edited entry files. Frozen ancestor metadata remains read-only.
 parent_receipt=json.loads((BASE/'build-device-receipt.json').read_text())
 for name,digest in parent_receipt['sources'].items():
  path=ROOT/name
  assert sha(path)==digest,'frozen parent source changed: '+name
  sources[name]=digest
 for mode in ('gnu-host','device'):
  dest=B/mode;dest.mkdir(exist_ok=True)
  args=next(r['command'] for r in prior if r['name']==mode+'-entry-main');args=args[:args.index('-o')]
  args=[x for x in args if not x.startswith('-I')]+['-I'+str(CHECKED),'-I'+str(P.parent)]
  for stem,src in [('entry-main',P/'native-src/entry-main.cpp'),('p49d_submit',P/'native-src/p49d_submit.cpp'),('expert_dispatch',checked_dispatch)]:
   commands.append(run([*args,'-o',dest/(stem+'.o'),'-c',src],mode+'-'+stem))
  link=list(next(r['command'] for r in prior if r['name']==mode+'-link'));link[link.index('-o')+1]=str(dest/'own-rt-iq3')
  for i,arg in enumerate(link):
   if arg.endswith('.o'):
    if Path(arg).name in ('entry-main.o','p49d_submit.o'):link[i]=str(dest/Path(arg).name)
    else:sources[str(Path(arg).relative_to(ROOT))]=sha(arg)
  link += [str(dest/'expert_dispatch.o')]
  if mode=='device':
   for image in (a.normal_image.resolve(),a.large_image.resolve()):
    assert image.is_file() and image.is_relative_to(P.parent)
    link += [str(image),'-Wl,-rpath,'+str(image.parent)]
    sources[str(image.relative_to(ROOT))]=sha(image)
  commands.append(run(link,mode+'-link'));artifacts[str((dest/'own-rt-iq3').relative_to(P))]=sha(dest/'own-rt-iq3')
 for f in [*P.glob('native/*'),*P.glob('native-src/*'),P/'prepare_sources.py',P/'build_engine.py',P/'source-copy-provenance.json',P.parent/'expert_dispatch.cpp',P.parent/'expert_dispatch.hpp']:
  sources[str(f.relative_to(ROOT))]=sha(f)
 for f in (P.parent/'build/checked').rglob('*'):
  if f.is_file():sources[str(f.relative_to(ROOT))]=sha(f)
 sources[str(mirror_path.relative_to(ROOT))]=sha(mirror_path)
 sources.update(json.loads((P/'source-copy-provenance.json').read_text())['sources'])
 save(P/'engine-commands.json',commands)
 save(P/'evidence/build.json',dict(passed=True,device_executed=False,sources=sources,artifacts=artifacts,commands=commands,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
 limits()
if __name__=='__main__':main()
