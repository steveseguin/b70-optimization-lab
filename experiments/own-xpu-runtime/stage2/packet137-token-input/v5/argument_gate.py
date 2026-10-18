"""Real v5 worker/config/oracle paths, native argv intercepted on CPU only.

Both registered windows and all five switch/reset selections are covered. The
separate legacy replay also exercises packet124c's eleven-window native shapes.
No synthetic device receipt can escape the temporary probe directory.
"""
import importlib.util,json,os,resource,subprocess,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from build_engine import P,ROOT,BASE,sha,save,limits
class Reached(BaseException):pass
class Forbidden(BaseException):pass
class LimitRefusal(BaseException):pass

def identity(kind):
 from common import sealed
 from bracket import load_config
 line=P/'lineage';config=P/'configs'/(kind+'.json')
 row=sealed(SimpleNamespace(lineage=line,seal=line/'screen-seal.json',binary=None,dispatch=None,profile='tp2',timing='token',placement='1'))
 row.update(lane='B',bracket=load_config(config),bracket_config=str(config),bracket_config_sha256=sha(config))
 return row

def probe(kind,check_limits=False):
 import exec_limits
 inherited=exec_limits.snapshot();row=identity(kind)
 oracle_command=['nice','-n','19','taskset','-c','8-15,24-31','python3','-B',str(P.parent/'shared_oracle.py'),'--require-complete']
 original_popen=subprocess.Popen;oracle_calls=[]
 import tp2_worker as worker
 with tempfile.TemporaryDirectory(prefix='p137-argv-') as directory:
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
  spec=importlib.util.spec_from_file_location('queue_library',P.parents[2]/'ops/lane-queue/lanequeue.py');q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)
  env={'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2','LD_LIBRARY_PATH':q.library_path()}
  monitor=SimpleNamespace(poll=lambda **k:None,register=lambda pid:None)
  with patch.object(subprocess,'Popen',side_effect=capture),patch.object(worker,'DeviceMonitor',return_value=monitor),patch.object(worker,'masked_environment',side_effect=lambda lane,*a,**k:masked_environment(lane,env)):
   try:worker.run(row,tmp/'run',4800)
   except Reached:pass
  assert len(seen)==2 and oracle_calls
  for rank,cmd in enumerate(seen):
   for key,value in [('--rank',str(rank)),('--context','4096'),('--max-new','64' if kind=='smoke' else '128'),('--seconds','4800'),('--draft-rank','1'),('--target-split','0'),('--retain-steps','none'),('--selection-sha256',sha(P/'lineage/selection.json'))]:assert cmd[cmd.index(key)+1]==value,(key,cmd)
   assert '--authorized-device-window' in cmd and '--mini' not in cmd
  return dict(passed=True,kind=kind,device_executed=False,native_exec_intercepted=True,argv=seen,real_oracle_commands=oracle_calls,limits_checked=check_limits,inherited_limits=inherited,final_limits=exec_limits.snapshot(),operational_admission_synthetic=True)

def native(cmd,selection):
 cmd=list(cmd);binary=str(P/'build/device/own-rt-iq3');cmd=cmd[cmd.index(binary):]
 cmd[0]=str(P/'build/full-shape/fixture');cmd.insert(1,'--startup109')
 if '--authorized-device-window' in cmd:cmd.remove('--authorized-device-window')
 from common import D
 inputs=ROOT/D.oracle_inputs()['prompts'][0]['input_bundle']
 with tempfile.TemporaryDirectory(prefix='p137-startup-') as d:
  for key,value in [('--output',d),('--native-nice','19'),('--selection',str(selection)),('--selection-sha256',sha(selection)),('--plan',str(inputs/'plan.tsv')),('--identity',str(inputs/'identity.tsv'))]:
   if key in cmd:cmd[cmd.index(key)+1]=value
  r=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
  assert r.returncode==0,r.stderr
  result=json.loads((Path(d)/'result.json').read_text());assert result['passed']
  return dict(passed=True,selection=str(selection),rank=cmd[cmd.index('--rank')+1],result=result,command=cmd)

def main():
 limits();rows=[];startups=[]
 for kind in ('smoke','bracket'):
  r=subprocess.run([sys.executable,'-B',str(P/'argument_gate.py'),'--probe',kind],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
  (P/'evidence'/('arguments-'+kind+'.log')).write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr
  row=json.loads(next(x.removeprefix('ARGUMENT_RESULT=') for x in r.stdout.splitlines() if x.startswith('ARGUMENT_RESULT=')));rows.append(row)
  for view in identity(kind)['bracket']['views']:
   for cmd in row['argv']:startups.append(native(cmd,Path(view['selection'])))
 sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'argument_gate.py',P/'tp2_worker.py',P/'bracket.py',P/'bracket_job.py',P/'exec_limits.py',P/'configs/smoke.json',P/'configs/bracket.json']}
 save(P/'evidence/argument-gate.json',dict(passed=True,device_executed=False,registered_windows=['smoke','bracket'],rows=rows,startups=startups,sources=sources))
 print('Both real worker launches, all six view paths / twelve native startup argv PASS')
if __name__=='__main__':
 if '--finite-negative' in sys.argv:
  resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,resource.RLIM_INFINITY))
  try:probe(sys.argv[-1],True)
  except LimitRefusal as e:
   assert 'RLIMIT_AS' in str(e);print('LIMITS_RESULT='+json.dumps(dict(passed=True,negative_control=True,refusal=str(e),device_executed=False)))
  else:raise AssertionError('finite cap accepted')
 elif '--limits-probe' in sys.argv:print('LIMITS_RESULT='+json.dumps(probe(sys.argv[-1],True)))
 elif '--probe' in sys.argv:print('ARGUMENT_RESULT='+json.dumps(probe(sys.argv[-1])))
 else:
  resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
