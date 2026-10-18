"""Real closed entry, unit gates, screen lifecycle and both native exec boundaries.

Only operational state and native execution are simulated. Every write goes to
private scratch; source admission, oracle, unit parsing, topology and env gates
run. No service, device open, signal or live queue write is possible.
"""
import contextlib,json,os,resource,subprocess,sys,tempfile,types
from pathlib import Path
from unittest.mock import patch
from p145_v5_build_engine import P,LOCAL,ROOT,sha,save
class Reached(BaseException):pass
class Forbidden(BaseException):pass

def probe(variant,kind,negative=None,lane="A"):
 import screen,bracket_job,readiness,p145_v5_compare as compare,tp2_worker,p145_v5_exec_limits as exec_limits
 from cpu_seal import verify
 from common import D
 from launch_env import apply
 verify();D.oracle_inputs()
 baseline=exec_limits.snapshot();seen=[];envs=[];units=[];reservations=[];oracle=[];result={}
 unit='screen-packet145-'+variant+'-'+kind+'-'+lane+'.service'
 group='0::/user.slice/user-1000.slice/user@1000.service/app.slice/'+unit+'\n'
 if negative=='unit':group=group.replace('screen-packet145','wrong-packet145')
 original_read=Path.read_text;original_open=Path.open;original_run=subprocess.run
 props=dict(Restart='no',SendSIGKILL='no',KillMode='process',ExitType='cgroup',TimeoutStopUSec='infinity')
 with tempfile.TemporaryDirectory(prefix='entry142-',dir=P/'evidence') as d:
  tmp=Path(d);out=tmp/'device';lock=tmp/'lane.lock'
  def read(path,*a,**k):return group if str(path)=='/proc/self/cgroup' else original_read(path,*a,**k)
  def opened(path,*a,**k):
   if str(path).endswith('/screen/v3/lane-'+lane+'.lock'):return original_open(lock,*a,**k)
   return original_open(path,*a,**k)
  oracle_cmd=['nice','-n','19','taskset','-c','8-15,24-31','python3','-B',str(LOCAL/'shared_oracle.py'),'--require-complete']
  def audit(event,args):
   if event=='open' and isinstance(args[0],(str,bytes)):
    path=Path(os.fsdecode(args[0])).absolute()
    if str(path).startswith('/dev/dri/'):raise Forbidden('device open')
    if (args[2] or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND) and path!=Path('/dev/null') and not path.resolve().is_relative_to(tmp):raise Forbidden('write outside scratch: '+str(path))
   if event in ('os.kill','os.killpg','os.system','os.exec'):raise Forbidden(event)
   if event in ('subprocess.Popen','os.posix_spawn') and list(args[1])!=oracle_cmd:raise Forbidden('unintercepted execution')
  sys.addaudithook(audit)
  def run(cmd,*a,**kw):
   if list(cmd)==oracle_cmd:
    oracle.append(cmd)
    # Execute only this read-only authority check with the real subprocess implementation.
    with patch.object(subprocess,'Popen',original_popen):return original_run(cmd,*a,**kw)
   if cmd[:3]==['/usr/bin/systemctl','--user','show']:
    units.append(cmd[3]);assert cmd[3]==unit
    return types.SimpleNamespace(returncode=0,stdout='\n'.join(k+'='+v for k,v in props.items()))
   raise Forbidden('unexpected run')
  class Lease:
   def __init__(self,lane,**kw):
    assert lane in ('A','B') and kw['window']=='screen';reservations.append(dict(lane=lane,window=kw['window']));self.record={};self.completed=False
   def __enter__(self):return self
   def __exit__(self,*a):return False
   def complete(self,**k):self.completed=True
  def capture(argv,*a,**kw):
   cmd=list(map(str,argv));exec_limits.check(baseline)
   seen.append(cmd);envs.append(dict(kw['env']))
   if len(seen)==2:raise Reached()
   return types.SimpleNamespace(pid=900001,poll=lambda:None)
  def worker(cmd,**kw):
   assert cmd[:3]==['/usr/bin/python3','-B',str(P/'tp2_worker.py')]
   identity=json.loads((out/'identity.json').read_text());monitor=types.SimpleNamespace(poll=lambda **k:None,register=lambda pid:None)
   with patch.dict(os.environ,kw['env'],clear=True),patch.object(subprocess,'Popen',side_effect=capture),patch.object(tp2_worker,'DeviceMonitor',return_value=monitor):
    # Install the real gate around the intercepted Popen; CPU caps must not leak.
    exec_limits.install()
    tp2_worker.run(identity,out/'run',4800)
   raise AssertionError('native boundary not reached')
  original_popen=subprocess.Popen
  with contextlib.ExitStack() as stack:
   for item in [patch.object(Path,'read_text',read),patch.object(Path,'open',opened),patch.object(subprocess,'run',side_effect=run),patch.object(subprocess,'Popen',side_effect=worker),
    patch.object(readiness,'verify_ready',side_effect=lambda **k:verify()),patch.object(compare,'load',return_value=dict(kind='smoke',passed=True,request_count=12,max_new=64)),
    patch.object(screen,'Reservation',Lease),patch.object(screen,'lane_gate'),patch.object(screen,'screen_teardown_admit'),
    patch.object(screen.fault_review,'validate',return_value=({},'','','CPU-only')),
    patch.object(screen.S,'journal',return_value=('','CPU-only')),patch.object(screen.S,'ldd_preflight',return_value={'synthetic':True}),
    patch.object(screen.SUPPORT,'storage',return_value={'synthetic':True}),patch.object(screen,'memory_admit',return_value={'synthetic':True}),
    patch.object(screen.W,'memory_fence',return_value={'synthetic':True}),patch.object(screen,'selected_clients',return_value={'synthetic':True}),
    patch.object(screen.shutil,'disk_usage',return_value=types.SimpleNamespace(free=50_000_000_000))]:stack.enter_context(item)
   if negative=='environment':
    # Deliberately poison after the actual entry constructs its closed environment.
    import launch_env
    def bad_env():row=apply();os.environ['PYTHONDONTWRITEBYTECODE']='1';return row
    stack.enter_context(patch.object(launch_env,'apply',side_effect=bad_env))
   try:
    code=bracket_job.main(['--variant',variant,'--kind',kind,'--lane',lane,'--output',str(out),'--fault-review',str(tmp/'review.json'),'--authorized-device-window'])
    assert code==0,original_read(out/'window.json') if (out/'window.json').exists() else str(code)
   except Reached:pass
   except (ValueError,AssertionError) as e:
    if negative:
     assert not seen;return dict(passed=True,device_executed=False,variant=variant,kind=kind,negative=negative,refusal=str(e))
    raise
  assert not negative and len(seen)==2 and oracle and units==[unit]
  for rank,argv in enumerate(seen):
   for key,value in [('--rank',str(rank)),('--context','4096'),('--max-new','64' if kind=='smoke' else '128'),('--seconds','4800'),('--draft-rank','1'),('--target-split','0'),('--retain-steps','none')]:assert argv[argv.index(key)+1]==value,(key,argv)
   assert '--authorized-device-window' in argv and '--mini' not in argv
  from devices import mask_for
  assert all(all(env.get(k)==v for k,v in mask_for(lane).items()) for env in envs),'wrong native lane mask'
  assert exec_limits.snapshot()==baseline
  return dict(passed=True,device_executed=False,variant=variant,kind=kind,unit=unit,unit_gate_real=True,unit_properties_gate_real=True,operational_context_synthetic=True,predecessor_synthetic=kind=='bracket',native_exec_intercepted=True,argv=seen,environments=envs,reservations=reservations,oracle_commands=oracle,limits_unchanged=True)

def main():
 from bracket_config import VALUES
 rows=[];negative=[]
 for variant in VALUES:
  for kind in ('smoke','bracket'):
   for lane in ('A','B'):
    for neg in (None,'unit','environment'):
     cmd=[sys.executable,'-B',str(P/'entry_gate.py'),'--probe',variant,kind,neg or 'positive',lane]
     r=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=240)
     log=P/'evidence'/('entry-'+variant+'-'+kind+'-'+lane+'-'+str(neg)+'.log');log.write_text(r.stdout+r.stderr);assert r.returncode==0,log.read_text()[-6000:]
     result=json.loads(next(x[len('ENTRY_RESULT='):] for x in r.stdout.splitlines() if x.startswith('ENTRY_RESULT=')))
     result['lane']=lane;(negative if neg else rows).append(result)
    print(variant,kind,lane,'entry PASS',flush=True)
 save(P/'evidence/entry-gate.json',dict(passed=True,device_executed=False,rows=rows,negative_controls=negative,sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'entry_gate.py',P/'bracket_job.py',P/'screen.py',P/'tp2_worker.py',P/'launch_env.py',P/'p145_ops_launch_env.py',P/'launch-environment.json',P/'p145_v5_exec_limits.py']}))
if __name__=='__main__':
 assert resource.getrlimit(resource.RLIMIT_AS)==(-1,-1)
 if '--probe' in sys.argv:print('ENTRY_RESULT='+json.dumps(probe(sys.argv[-4],sys.argv[-3],None if sys.argv[-2]=='positive' else sys.argv[-2],sys.argv[-1])))
 else:main()
