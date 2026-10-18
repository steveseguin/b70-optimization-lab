"""Incremental build; commands run under packet94's serial compile lock."""
import hashlib,importlib.util,json,os,resource,shutil,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[4];STAGE=P.parents[1]
BASE=STAGE/'packet111-record-bundle';B=P/'build';CHECKED=BASE/'build/checked'/BASE.relative_to(ROOT)
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
 assert sum(f.stat().st_size for f in P.parent.rglob('*') if f.is_file() and 'build' in f.parts and not f.is_symlink())<=250_000_000
def compiler_turn():
 path=STAGE/'packet94-hc-norm-fusion/compile_turn.py'
 spec=importlib.util.spec_from_file_location('p117_compile_turn',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 return m.turn()
def run(cmd,name):
 limits();B.mkdir(exist_ok=True);started=time.monotonic()
 with compiler_turn(),(B/(name+'.log')).open('w') as log:
  subprocess.run(list(map(str,cmd)),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1200)
 return dict(name=name,command=list(map(str,cmd)),seconds=time.monotonic()-started)
def main():
 limits();B.mkdir(exist_ok=True)
 prior=json.loads((BASE/'engine-commands.json').read_text());commands=[];sources={};artifacts={}
 # Candidate source includes the exact frozen p60/p73 types from packet111.
 candidate=P.parent/'hc_gate.hpp'
 text=candidate.read_text()
 import re
 def include(m):
  leaf=Path(m[1]).name
  target=CHECKED/leaf
  if not target.is_file():raise ValueError('candidate include is not in checked packet111: '+leaf)
  return '#include '+json.dumps(str(target))
 text=re.sub(r'^\s*#include\s*"([^"\n]+)"',include,text,flags=re.M)
 spec=importlib.util.spec_from_file_location('p117_submission_overlay',BASE/'submission_overlay.py')
 overlay=importlib.util.module_from_spec(spec);spec.loader.exec_module(overlay)
 text=overlay.apply_submission_overlay(candidate,text)
 (B/'hc_gate_checked.hpp').write_text(text)
 sources[str(candidate.relative_to(ROOT))]=sha(candidate)
 sources[str((B/'hc_gate_checked.hpp').relative_to(ROOT))]=sha(B/'hc_gate_checked.hpp')
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
  for stem,src in [('entry-main',P/'native-src/entry-main.cpp'),('p49d_submit',P/'native-src/p49d_submit.cpp'),('hc_submit',P/'native-src/hc_submit.cpp')]:
   commands.append(run([*args,'-o',dest/(stem+'.o'),'-c',src],mode+'-'+stem))
  link=list(next(r['command'] for r in prior if r['name']==mode+'-link'));link[link.index('-o')+1]=str(dest/'own-rt-iq3')
  for i,arg in enumerate(link):
   if arg.endswith('.o'):
    if Path(arg).name in ('entry-main.o','p49d_submit.o'):link[i]=str(dest/Path(arg).name)
    else:sources[str(Path(arg).relative_to(ROOT))]=sha(arg)
  link += [str(dest/'hc_submit.o')]
  commands.append(run(link,mode+'-link'));artifacts[str((dest/'own-rt-iq3').relative_to(P))]=sha(dest/'own-rt-iq3')
 for f in [*P.glob('native/*'),*P.glob('native-src/*'),P/'prepare_sources.py',P/'build_engine.py',P/'source-copy-provenance.json',P/'native-src/hc_submit.cpp',P/'native-src/hc_submit.hpp']:
  sources[str(f.relative_to(ROOT))]=sha(f)
 sources.update(json.loads((P/'source-copy-provenance.json').read_text())['sources'])
 save(P/'engine-commands.json',commands)
 save(P/'evidence/build.json',dict(passed=True,device_executed=False,sources=sources,artifacts=artifacts,commands=commands,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
 limits()
if __name__=='__main__':main()
