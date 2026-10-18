"""Execute the real worker to both intercepted native argv; no device exec.

Follows packet124b's argument_gate.py: real parser/selection/oracle/placement,
synthetic operational monitor, temporary writes, hard native-exec interception.
"""
import contextlib,importlib.util,json,os,resource,shutil,subprocess,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from build131 import P,ROOT,sha,save,limits
class Reached(BaseException):pass
class Forbidden(BaseException):pass
class LimitRefusal(BaseException):pass
def sources():
 names=('arguments131.py','run131.py','smoke_worker.py','grid_worker.py','worker.py','exec_limits.py','bootstrap.py','placement.py','placement-policy.json','dependency-pins.json','shared-wrapper-pin.json')
 files=[*(P/n for n in names),*(P/'selections'/v/n for v in ('control','candidate') for n in ('selection.json','screen-seal.json'))]
 return {str(f.relative_to(ROOT)):sha(f) for f in files}

def probe(check_limits=False,index=-1):
 import exec_limits
 inherited=exec_limits.snapshot()
 from run131 import view,ORDER
 VIEW=view("candidate" if index==-1 else ORDER[index])
 from bootstrap import install
 install()
 from common import sealed
 identity=sealed(SimpleNamespace(lineage=VIEW,seal=VIEW/'screen-seal.json',binary=None,dispatch=None,profile='tp2',timing='token',placement='1'))
 identity['lane']='B'
 if index==-1:
  import smoke_worker as worker
 else:
  from bootstrap import WRAPPER
  spec=importlib.util.spec_from_file_location("p131_grid_worker",P/"grid_worker.py");worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
 with tempfile.TemporaryDirectory(prefix='p128b-argv-') as directory:
  tmp=Path(directory)
  def audit(event,values):
   if event=='open' and isinstance(values[0],(str,bytes)):
    path=Path(os.fsdecode(values[0])).absolute()
    if str(path).startswith('/dev/dri/'):raise Forbidden('device open forbidden')
    if (values[2] or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND) and path!=Path('/dev/null') and not path.resolve().is_relative_to(tmp):raise Forbidden('write outside CPU scratch: '+str(path))
   if event in ('subprocess.Popen','os.system','os.exec','os.posix_spawn'):raise Forbidden('execution forbidden')
  sys.addaudithook(audit);observations=[]
  def capture(cmd,*a,**kw):
   if check_limits:
    try:exec_limits.check(inherited)
    except AssertionError as e:raise LimitRefusal(str(e)) from e
   observations.append(list(map(str,cmd)))
   if len(observations)==2:raise Reached()
   return SimpleNamespace(pid=900001,poll=lambda:None)
  monitor=SimpleNamespace(poll=lambda **k:None,register=lambda pid:None)
  from devices import masked_environment
  spec=importlib.util.spec_from_file_location("p128_queue",P.parents[1]/"ops/lane-queue/lanequeue.py");q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q);ldp=q.library_path()
  guard_observations=[]
  original_check=exec_limits.check
  def checked_limits(baseline):
   try:return original_check(baseline)
   except AssertionError as error:
    if 'RLIMIT_AS' not in str(error):raise
    assert not observations and not guard_observations
    # Escape the worker's normal device-error teardown in this CPU-only test.
    # The real guard has already rejected the unchanged limit check.
    raise LimitRefusal(str(error)) from error
  with patch.object(subprocess,'Popen',side_effect=capture),patch.object(worker,'DeviceMonitor',return_value=monitor),patch.object(worker,'masked_environment',side_effect=lambda lane,*a,**k:masked_environment(lane,{'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2','LD_LIBRARY_PATH':ldp})):
   if check_limits:
    exec_limits.check=checked_limits
    exec_limits.install(lambda argv,baseline:guard_observations.append(dict(argv=argv,limits=baseline)))
   try:worker.run(identity,tmp/'run',1800 if index==-1 else 3600)
   except Reached:pass
   except AssertionError as error:
    if check_limits and 'RLIMIT_AS' in str(error):raise LimitRefusal(str(error)) from error
    raise
  assert len(observations)==2
  for rank,cmd in enumerate(observations):
   for key,value in [('--rank',str(rank)),('--timing','token'),('--max-new','64' if index==-1 else '128'),('--seconds','1800' if index==-1 else '3600'),('--selection-sha256',sha(VIEW/'selection.json')),('--draft-rank','1'),('--target-split','0'),('--context','4096'),('--retain-steps','none')]:assert cmd[cmd.index(key)+1]==value,(key,cmd)
   assert '--authorized-device-window' in cmd and '--mini' not in cmd
  if check_limits:
   assert len(guard_observations)==2 and all(row['limits']==inherited for row in guard_observations)
  return dict(passed=True,index=index,device_executed=False,native_exec_intercepted=True,argv=observations,operational_admission_synthetic=True,limits_checked=check_limits,actual_guard_observations=guard_observations,inherited_limits=inherited,final_limits=exec_limits.snapshot())


def main():
 results=[]
 for index in range(-1,5):
  cp=subprocess.run([sys.executable,'-B',str(P/'arguments131.py'),'--probe',str(index)],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
  (P/'evidence'/('arguments131-'+str(index)+'.log')).write_text(cp.stdout+cp.stderr)
  assert cp.returncode==0,cp.stderr
  result=json.loads(next(x.removeprefix('ARGUMENT_RESULT=') for x in cp.stdout.splitlines() if x.startswith('ARGUMENT_RESULT=')))
  result['index']=index;results.append(result)
 save(P/'evidence/arguments131.json',dict(passed=True,device_executed=False,windows=results,sources=sources()))
 print('All six registered windows reach both intercepted native argv')
if __name__=='__main__':
 if '--limits-probe' in sys.argv:
  print('LIMITS_RESULT='+json.dumps(probe(check_limits=True,index=int(sys.argv[-1]))))
 elif '--finite-negative' in sys.argv:
  resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,resource.RLIM_INFINITY))
  try:probe(check_limits=True,index=int(sys.argv[-1]))
  except LimitRefusal as e:
   assert 'RLIMIT_AS' in str(e)
   print('LIMITS_RESULT='+json.dumps(dict(passed=True,index=int(sys.argv[-1]),negative_control=True,refusal=str(e),device_executed=False)))
  else:raise AssertionError('finite cap not refused')
 else:
  from build131 import cpu_main
  cpu_main()
  if '--probe' in sys.argv:print('ARGUMENT_RESULT='+json.dumps(probe(index=int(sys.argv[-1]))))
  else:main()
