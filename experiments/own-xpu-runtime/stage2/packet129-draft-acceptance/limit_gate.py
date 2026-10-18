"""Check actual runtime imports and intercept exec before any native launch."""
import json,os,resource,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent
def snapshot():
 return {str(getattr(resource,n)):list(resource.getrlimit(getattr(resource,n))) for n in dir(resource) if n.startswith('RLIMIT_')}
def probe(finite=False):
 before=snapshot()
 import run_screen,worker,exec_limits
 assert snapshot()==before,'runtime import changed resource limits'
 observed=[]
 class Intercept(BaseException):pass
 def capture(argv,limits):observed.append(dict(argv=argv,limits=limits));raise Intercept()
 exec_limits.install(observer=capture)
 if finite:resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 try:subprocess.Popen([str(P/'selections/acceptance/build/device/own-rt-iq3'),'--authorized-device-window'])
 except Intercept:
  assert not finite and len(observed)==1 and snapshot()==before
  return dict(passed=True,device_executed=False,native_exec_intercepted=True,inherited_limits_preserved=True)
 except AssertionError as error:
  assert finite and not observed and 'finite RLIMIT_AS' in str(error)
  return dict(passed=True,device_executed=False,finite_cpu_limit_refused=True)
 raise AssertionError('native boundary was not intercepted')
def main():
 if '--probe' in sys.argv:print(json.dumps(probe('--finite' in sys.argv)));return
 assert resource.getrlimit(resource.RLIMIT_AS)==(resource.RLIM_INFINITY,resource.RLIM_INFINITY),'invoke this small import probe outside cpu_prepare caps'
 results=[]
 for extra in ([],['--finite']):
  r=subprocess.run([sys.executable,'-B',str(P/'limit_gate.py'),'--probe',*extra],stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True,timeout=120)
  results.append(json.loads(r.stdout))
 import hashlib
 row=dict(passed=True,device_executed=False,checks=results,sources={str((P/n).relative_to(P.parents[3])):hashlib.sha256((P/n).read_bytes()).hexdigest() for n in ('limit_gate.py','run_screen.py','worker.py','exec_limits.py')})
 (P/'evidence/limit-gate.json').write_text(json.dumps(row,indent=2)+'\n')
 print('Runtime imports preserve all inherited limits; native boundary rejects finite CPU cap')
if __name__=='__main__':main()
