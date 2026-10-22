"""Real v5 worker/config/oracle paths, native argv intercepted on CPU only.

Packet185: all five fresh-load view rows (both selections), both lanes.
No synthetic device receipt can escape the temporary probe directory.
"""
import importlib.util,json,os,resource,subprocess,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from p185_v5_build_engine import P,ROOT,BASE,sha,save,limits
class Reached(BaseException):pass
class Forbidden(BaseException):pass
class LimitRefusal(BaseException):pass

def identity(index,lane="A"):
 from common import sealed
 from bracket import load_config
 from bracket_config import VIEWS
 variant=VIEWS[int(index)];line=P/'lineage'/variant;config=P/'configs'/('view'+str(int(index))+'-'+variant+'.json')
 row=sealed(SimpleNamespace(lineage=line,seal=line/'screen-seal.json',binary=None,dispatch=None,profile='tp2',timing='token',placement='1'))
 row.update(lane=lane,bracket=load_config(config),bracket_config=str(config),bracket_config_sha256=sha(config))
 return row

def probe(index,check_limits=False,lane="A"):
 import p185_v5_exec_limits as exec_limits
 from bracket_config import VIEWS
 variant=VIEWS[int(index)];inherited=exec_limits.snapshot();row=identity(index,lane)
 oracle_command=['nice','-n','19','taskset','-c','8-15,24-31','python3','-B',str(P.parent/'shared_oracle.py'),'--require-complete']
 original_popen=subprocess.Popen;oracle_calls=[]
 import tp2_worker as worker
 with tempfile.TemporaryDirectory(prefix='p142-argv-') as directory:
  tmp=Path(directory)
  def audit(event,args):
   if event=='open' and isinstance(args[0],(str,bytes)):
    path=Path(os.fsdecode(args[0])).absolute()
    if str(path).startswith('/dev/dri/'):raise Forbidden('device open forbidden')
    if (args[2] or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND) and path!=Path('/dev/null') and not path.resolve().is_relative_to(tmp):raise Forbidden('write outside scratch: '+str(path))
   if event in ('subprocess.Popen','os.posix_spawn') and list(args[1])==oracle_command:return
   if event in ('subprocess.Popen','os.system','os.exec','os.posix_spawn'):raise Forbidden('execution forbidden')
  sys.addaudithook(audit);seen=[]
  def capture(cmd,*a,**kw):
   if list(map(str,cmd))==oracle_command:
    oracle_calls.append(oracle_command);return original_popen(cmd,*a,**kw)
   if check_limits:
    try:exec_limits.check(inherited)
    except AssertionError as e:raise LimitRefusal(str(e)) from e
   seen.append(list(map(str,cmd)))
   if len(seen)==2:raise Reached()
   return SimpleNamespace(pid=900001,poll=lambda:None)
  from devices import masked_environment
  env=json.loads((P/'launch-environment.json').read_text())
  monitor=SimpleNamespace(poll=lambda **k:None,register=lambda pid:None)
  with patch.object(subprocess,'Popen',side_effect=capture),patch.object(worker,'DeviceMonitor',return_value=monitor),patch.object(worker,'masked_environment',side_effect=lambda lane,*a,**k:masked_environment(lane,env)):
   try:worker.run(row,tmp/'run',900)
   except Reached:pass
  assert len(seen)==2 and oracle_calls
  for rank,cmd in enumerate(seen):
   for key,value in [('--rank',str(rank)),('--context','4096'),('--max-new','64'),('--seconds','900'),('--draft-rank','1'),('--target-split','0'),('--retain-steps','none'),('--selection-sha256',sha(P/'lineage'/variant/'selection.json'))]:assert cmd[cmd.index(key)+1]==value,(key,cmd)
   assert '--authorized-device-window' in cmd and '--mini' not in cmd
  return dict(passed=True,kind='view',view_index=int(index),variant=variant,device_executed=False,native_exec_intercepted=True,argv=seen,real_oracle_commands=oracle_calls,limits_checked=check_limits,inherited_limits=inherited,final_limits=exec_limits.snapshot(),operational_admission_synthetic=True)

if __name__=='__main__':
 index,lane=sys.argv[-2:]
 if '--finite-negative' in sys.argv:
  resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,resource.RLIM_INFINITY))
  try:probe(index,True,lane)
  except LimitRefusal as e:print('LIMITS_RESULT='+json.dumps(dict(passed=True,negative_control=True,refusal=str(e),device_executed=False)))
  else:raise AssertionError('finite cap accepted')
 else:print('LIMITS_RESULT='+json.dumps(probe(index,True,lane)))
