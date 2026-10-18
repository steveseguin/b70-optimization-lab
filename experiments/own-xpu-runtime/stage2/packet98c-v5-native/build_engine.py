"""Packet98 serial native-entry build; unchanged kernels linked by exact hash."""
import hashlib,importlib.util,json,os,resource,shutil,subprocess,time
from pathlib import Path
from native_source import P,ROOT,BASE,generate
B=P/'build'
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def save(path,row):
 Path(path).parent.mkdir(parents=True,exist_ok=True);Path(path).write_text(json.dumps(row,indent=2)+'\n')
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 assert shutil.disk_usage('/').free>=12_000_000_000,'root below 12 GB'
 total=0
 for f in B.rglob('*'):
  try:
   if f.is_file():total+=f.stat().st_size
  except FileNotFoundError:pass  # another CPU gate just retained its scratch
 assert total<=300_000_000,'packet98c build above 300 MB'
def compiler_turn():
 path=P.parent/'packet94-hc-norm-fusion/compile_turn.py'
 spec=importlib.util.spec_from_file_location('packet94_compile_turn',path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 return mod.turn()
def main():
 limits()
 from restore_rope import restore
 restore();native=generate();prior=json.loads((BASE/'engine-commands.json').read_text())
 parent=json.loads((BASE/'build-device-receipt.json').read_text());sources={name:digest for name,digest in parent['sources'].items() if not name.endswith(('selection.json','evidence/object-identity.json'))};commands=[];artifacts={}
 for name,digest in sources.items():assert sha(ROOT/name)==digest,name
 sources[str((BASE/'engine-commands.json').relative_to(ROOT))]=sha(BASE/'engine-commands.json')
 for f in [*(P/'sources').rglob('*'),P/'source-copy-provenance.json',P/'native_source.py',P/'build_engine.py',*P.glob('native/*'),*native.glob('*')]:
  if f.is_file():sources[str(f.relative_to(ROOT))]=sha(f)
 with compiler_turn():
  for mode in ('gnu-host','device'):
   dest=B/mode;dest.mkdir(exist_ok=True)
   args=next(r['command'] for r in prior if r['name']==mode+'-entry-main');args=args[:args.index('-o')]
   compile_cmd=[*args,'-o',str(dest/'entry-main.o'),'-c',str(native/'entry-main.cpp')]
   link=list(next(r['command'] for r in prior if r['name']==mode+'-link'))
   link[link.index('-o')+1]=str(dest/'own-rt-iq3')
   for i,arg in enumerate(link):
    if arg.endswith('/entry-main.o'):link[i]=str(dest/'entry-main.o')
    elif arg.endswith('.o'):sources[str(Path(arg).relative_to(ROOT))]=sha(arg)
   for name,cmd in ((mode+'-entry-main',compile_cmd),(mode+'-link',link)):
    limits();start=time.monotonic()
    with (B/(name+'.log')).open('w') as log:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1200)
    commands.append(dict(name=name,command=cmd,seconds=time.monotonic()-start));print(name,'PASS',flush=True)
   artifacts[str((dest/'own-rt-iq3').relative_to(P))]=sha(dest/'own-rt-iq3')
 limits();save(P/'evidence/build.json',dict(passed=True,device_executed=False,sources=sources,artifacts=artifacts,commands=commands,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
if __name__=='__main__':main()
