"""Small standalone CPU build; packet94's unmodified compiler turn gate."""
import hashlib,json,os,resource,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];B=P/'build'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
def main():
 from compile_turn import turn
 limits();os.environ['TMPDIR']=str(B/'tmp')
 for row in json.loads((P/'source-lineage.json').read_text()):
  assert sha(ROOT/row['copy'])==row['sha256']==sha(ROOT/row['source'])
 compiler='/opt/intel/oneapi/compiler/2026.0/bin/icpx'
 flags=['-std=c++20','-O2','-fsycl','-fno-fast-math','-ffp-contract=off','-DP56X_SLEEP20=0','-I'+str(P/'sources'),'-I/usr/include','-pthread']
 commands=[];objects=[]
 for source in ['microbench.cpp','sources/owner.cpp','sources/owner_retire.cpp','sources/single_device.cpp','sources/host_wait_mode.cpp']:
  obj=B/(Path(source).stem+'.o');cmd=[compiler,*flags,'-c',str(P/source),'-o',str(obj)];commands.append(cmd)
  with turn(),(B/(obj.stem+'.log')).open('w') as log:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
  objects.append(str(obj));print(source,'compiled',flush=True)
 cmd=[compiler,'-fsycl',*objects,'-lze_loader','-pthread','-o',str(B/'microbench')];commands.append(cmd)
 with turn(),(B/'link.log').open('w') as log:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
 sources={str(f.relative_to(ROOT)):sha(f) for f in [*sorted((P/'sources').glob('*')),P/'microbench.cpp',P/'build_engine.py',P/'compile_turn.py',P/'source-lineage.json']}
 size=sum(f.stat().st_size for f in B.rglob('*') if f.is_file());assert size<=200_000_000
 (P/'evidence/microbench-build.json').write_text(json.dumps(dict(passed=True,device_executed=False,sources=sources,artifacts={'build/microbench':sha(B/'microbench')},commands=commands,build_bytes=size,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss),indent=2)+'\n')
 print('PASS CPU compile; build bytes',size,flush=True)
if __name__=='__main__':main()
