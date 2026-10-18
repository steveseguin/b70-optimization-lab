"""One bounded CPU preparation sequence; failures stop rather than retry."""
import subprocess,sys,time
from build_engine import P,sha,save,limits
def main():
 limits();rows=[];tag=str(time.time_ns())
 for name in ('refresh_kernels.py','full_shape.py','reset_gate.py','protocol_gate.py','startup116.py'):
  path=P/'evidence'/('cpu-'+tag+'-'+name+'.log');start=time.monotonic()
  print('CPU stage',name,flush=True)
  with path.open('w') as log:
   cp=subprocess.run([sys.executable,'-B',str(P/name)],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
  rows.append(dict(stage=name,returncode=cp.returncode,seconds=time.monotonic()-start,log=str(path.relative_to(P)),log_sha256=sha(path)))
  save(P/'evidence/cpu-sequence.json',dict(passed=cp.returncode==0 and len(rows)==5,device_executed=False,stages=rows))
  if cp.returncode:raise SystemExit(cp.returncode)
  limits();print('CPU stage',name,'PASS',flush=True)
if __name__=='__main__':main()
