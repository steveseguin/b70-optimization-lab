"""Explicit CPU preparation entry. Never call this from a device job."""
import os,resource,subprocess,sys,time,json
from pathlib import Path
P=Path(__file__).resolve().parent
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 os.environ['OMP_NUM_THREADS']='2'
 for script in sys.argv[1:]:
  start=time.monotonic();log=P/'evidence'/(script+'.log')
  with log.open('w') as out:r=subprocess.run([sys.executable,'-B',str(P/script)],stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,cwd=P)
  (P/'evidence'/(script+'.status.json')).write_text(json.dumps(dict(passed=r.returncode==0,returncode=r.returncode,seconds=time.monotonic()-start,device_executed=False))+'\n')
  print(script,r.returncode,flush=True)
  if r.returncode:raise SystemExit(r.returncode)
