"""Real confirm entry through CPU admission/oracle to both intercepted rank commands."""
import json,subprocess,sys
from pathlib import Path
from unittest.mock import patch
from source_decision import O,P,ROOT,sha,save
sys.path.insert(0,str(P))
class Reached(BaseException):pass

def probe(index,old=False):
 import contextlib,os,tempfile,types
 import confirm136
 from bootstrap import install
 install()
 import common,smoke_screen,run_screen,smoke_validation,compare136,cpu_seal
 screen=smoke_screen if index==-1 else run_screen.screen
 calls=[];result={};reservations=[];environments=[];topologies=[]
 if old:
  # Execute the original entry's actual source with the same globals/root.
  old_source=subprocess.run(['git','show','3dfcff0ca:'+str((P.with_name('packet136-record-bundle')/'confirm136.py').relative_to(ROOT))],stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True).stdout
  original=types.ModuleType('old_confirm136');original.__dict__.update(confirm136.__dict__)
  old_source=old_source.replace('packet136-orchestration','packet139-orchestration')
  exec(compile(old_source,str(P/'confirm136.py'),'exec'),original.__dict__)
  original.output=confirm136.output;original.admission=confirm136.admission
  confirm136=original
 with tempfile.TemporaryDirectory(prefix='p136b-startup-') as tmp:
  tmp=Path(tmp);here=tmp/'screen/v4-lanes';here.mkdir(parents=True);(here.parent/'v3').mkdir()
  (here/'placement-validation').symlink_to(screen.HERE/'placement-validation',target_is_directory=True)
  output=here/'evidence/job'
  from argument_gate import sandbox
  # Real CPU admission/oracle runs before the write/exec sandbox is installed.
  confirm136.admission()
  from proposal_plan import proposal
  import lanequeue
  from confirm136 import LIBRARIES
  launch=lanequeue.command(proposal()[0],'/synthetic/CPU-review.json',tmp/'receipt.json',LIBRARIES)
  unit=next(x.split('=',1)[1] for x in launch if x.startswith('--unit='))+'.service'
  assert unit=='screen-packet139-smoke-A.service'
  cgroup=f'0::/user@{os.getuid()}.service/{unit}'
  # Execute both real unit policies, with only systemd's response substituted.
  original_read_text=Path.read_text
  def read_text(path,*a,**kw):
   if path==Path('/proc/self/cgroup'):return cgroup
   return original_read_text(path,*a,**kw)
  unit_calls=[]
  def systemctl(cmd,**kwargs):
   assert cmd[:4]==['/usr/bin/systemctl','--user','show',unit],cmd
   unit_calls.append(cmd)
   return subprocess.CompletedProcess(cmd,0,'Restart=no\nSendSIGKILL=no\nKillMode=process\nExitType=cgroup\nTimeoutStopUSec=infinity\n','')
  sandbox(tmp)
  parser=screen.parser;masked=screen.masked_environment;topology=screen.topology_admit
  def parse():
   ap=parser();original=ap.parse_args
   def parsed(argv):
    args=original(argv)
    assert args.authorized_device_window and not args.plan and args.lane=='A'
    assert args.output==confirm136.output(index)
    expected=confirm136.view('candidate' if index==-1 else confirm136.ORDER[index])
    assert args.lineage==expected and args.seal==expected/'screen-seal.json'
    calls.append(dict(argv=argv,seal_sha256=common.sealed(args)['seal_sha256']))
    args.output=output
    return args
   ap.parse_args=parsed;return ap
  def environment(lane):
   value=masked(lane);environments.append(dict(source=dict(os.environ),native=value));return value
  def topo(lane):
   value=topology(lane);topologies.append(value);return value
  class Lease:
   def __init__(self,lane,**kwargs):
    assert lane=='A' and kwargs['window']=='screen'
    reservations.append(dict(lane=lane,window=kwargs['window'],scope=screen.admission_scope(lane,'screen')));self.record={}
   def __enter__(self):return self
   def __exit__(self,*a):return False
  def worker(cmd,**kwargs):
   from types import SimpleNamespace
   import importlib.util
   assert cmd[0:2]==['/usr/bin/python3','-B']
   assert Path(cmd[2])==P/('smoke_worker.py' if index==-1 else 'worker.py')
   assert kwargs['env']==environments[-1]['native']
   if index==-1:
    import smoke_worker as native_worker
   else:
    spec=importlib.util.spec_from_file_location('entry_grid_worker',P/'grid_worker.py')
    native_worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(native_worker)
   observations=[];native_environments=[]
   def capture(argv,*a,**kw):
    observations.append(list(map(str,argv)));native_environments.append(dict(kw['env']))
    if len(observations)==2:raise Reached()
    return SimpleNamespace(pid=900001,poll=lambda:None)
   monitor=SimpleNamespace(poll=lambda **k:None,register=lambda pid:None)
   identity=json.loads((output/'identity.json').read_text())
   with patch.dict(os.environ,kwargs['env'],clear=True),patch.object(subprocess,'Popen',side_effect=capture),patch.object(native_worker,'DeviceMonitor',return_value=monitor):
    try:native_worker.run(identity,output/'run',1800 if index==-1 else 3600)
    except Reached:pass
   assert len(observations)==2
   for rank,argv in enumerate(observations):
    for key,value in [('--rank',str(rank)),('--timing','token'),('--max-new','64' if index==-1 else '128'),('--seconds','1800' if index==-1 else '3600'),('--selection-sha256',identity['selection_sha256']),('--draft-rank','1'),('--target-split','0'),('--context','4096'),('--retain-steps','none')]:
     assert argv[argv.index(key)+1]==value,(key,argv)
    assert '--authorized-device-window' in argv and '--mini' not in argv
   result.update(passed=True,index=index,device_executed=False,native_exec_intercepted=True,argv=observations,native_environments=native_environments)
   raise Reached()
  with contextlib.ExitStack() as stack:
   for item in [patch.object(confirm136,'admission'),patch.object(smoke_validation,'require_smoke'),patch.object(compare136,'load'),
    patch.object(screen,'parser',side_effect=parse),patch.object(screen,'HERE',here),patch.object(screen,'OUTPUT_ROOT',here),
    patch.object(screen,'DEFAULT_DRAIN_ROOT',tmp/'drain'),patch.object(screen,'Reservation',Lease),
    patch.object(os,'getpriority',return_value=0),patch.object(os,'sched_getaffinity',return_value={0,1,2,3,16,17,18,19}),patch.object(screen,'screen_teardown_admit'),
    patch.object(Path,'read_text',read_text),patch.object(subprocess,'run',side_effect=systemctl),
    patch.object(screen.fault_review,'validate',return_value=({},'','','CPU-only')),
    patch.object(screen.S,'journal',return_value=('','CPU-only')),patch.object(screen.S,'ldd_preflight',return_value={'synthetic':True}),
    patch.object(screen.SUPPORT,'storage',return_value={'synthetic':True}),patch.object(screen.M,'meminfo',return_value={'MemAvailable':128*1024**3}),
    patch.object(screen.W,'memory_fence',return_value={'synthetic':True}),patch.object(screen,'selected_clients',return_value={'synthetic':True}),
    patch.object(screen,'masked_environment',side_effect=environment),patch.object(screen,'topology_admit',side_effect=topo),
    patch.object(subprocess,'Popen',side_effect=worker)]:stack.enter_context(item)
   try:
    confirm136.main(['--index',str(index),'--output',str(confirm136.output(index)),'--fault-review','/synthetic/CPU-review.json','--authorized-device-window'])
   except Reached:pass
   except ValueError as error:
    if old and str(error)=='closed environment required':
     assert not result and not topologies
     return dict(passed=True,old_entry_refused=True,reason=str(error),device_executed=False,index=index)
    raise
  assert not old and result['native_exec_intercepted'] and len(result['argv'])==2
  assert len(environments)==len(topologies)==len(reservations)==1
  result.update(entry='confirm136.main -> real screen.main -> worker.run',entry_calls=calls,readiness_verified=True,real_complete_oracle=True,
   service_wrapper_synthetic=True,real_unit_gate=True,unit=unit,unit_calls=unit_calls,launch_command=launch,predecessors_synthetic=index>=0,environments=environments,topologies=topologies,reservations=reservations)
  return result

def chain_probe():
 import os,shlex
 from argument_gate import probe
 from bootstrap import install
 install()
 from devices import masked_environment
 from confirm136 import LIBRARIES
 tokens=shlex.split((O/'device-entry.sh').read_text().replace('\\\n',' '))
 begin=tokens.index('env');end=tokens.index('python3',begin)
 environment=dict(token.split('=',1) for token in tokens[begin+2:end])
 assert environment==dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2',LD_LIBRARY_PATH=LIBRARIES)
 # Python may add LC_CTYPE when started by env -i; no shell metadata is copied.
 assert dict(os.environ)==environment or dict(os.environ)==dict(environment,LC_CTYPE='C.UTF-8')
 masked_environment('A')
 result=probe('WS128',entry=True)
 assert result['startup']['reservation']==dict(lane='A',window='WS128',scope='whole-host')
 assert result['startup']['topology']['device_nodes_opened'] is False
 result.update(environment=dict(os.environ),entry='device-entry.sh environment -> chain_entry.main -> window',real_complete_oracle=True)
 return result
def sources():
 from source_gate136 import verify_sources
 return verify_sources({str(f.relative_to(ROOT)):sha(f) for f in [O/'entry_gate.py',O/'verify_cpu.py',P/'confirm136.py',P/'arguments136.py',P/'compare136.py',P/'source_gate136.py',O/'argument_gate.py',O/'chain_entry.py',O/'device-entry.sh']})
def verify():
 row=json.loads((O/'evidence/confirm-entries.json').read_text())
 assert row['passed'] and row['device_executed'] is False and row['sources']==sources()
 assert [r['index'] for r in row['windows']]==[-1]
 assert all(r['native_exec_intercepted'] and len(r['argv'])==2 and len(r['environments'])==len(r['topologies'])==len(r['reservations'])==1 for r in row['windows'])
 assert row['old_entry']['old_entry_refused'] and row['chain']['native_exec_intercepted']
 return row
def main():
 rows=[]
 for i in (-1,):
  cp=subprocess.run([sys.executable,'-B',str(O/'entry_gate.py'),'--probe',str(i)],env=__import__('startup_plan').environment(),stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=240)
  (O/'evidence'/f'confirm-entry-{i}.log').write_text(cp.stdout+cp.stderr)
  assert cp.returncode==0,cp.stdout[-1000:]+cp.stderr[-4000:]
  rows.append(json.loads(next(x.removeprefix('ENTRY_RESULT=') for x in cp.stdout.splitlines() if x.startswith('ENTRY_RESULT='))))
  print('confirm entry',i,'reaches both intercepted native calls',flush=True)
 extra={}
 for mode in ('old','chain'):
  from confirm136 import LIBRARIES
  env=dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2',LD_LIBRARY_PATH=LIBRARIES)
  cp=subprocess.run([sys.executable,'-B',str(O/'entry_gate.py'),'--'+mode],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=240)
  (O/'evidence'/('entry-'+mode+'.log')).write_text(cp.stdout+cp.stderr)
  assert cp.returncode==0,cp.stderr[-5000:]
  extra[mode]=json.loads(next(x.removeprefix('ENTRY_RESULT=') for x in cp.stdout.splitlines() if x.startswith('ENTRY_RESULT=')))
 save(O/'evidence/confirm-entries.json',dict(passed=True,device_executed=False,windows=rows,old_entry=extra['old'],chain=extra['chain'],sources=sources()));verify()
if __name__=='__main__':
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 if '--probe' in sys.argv:print('ENTRY_RESULT='+json.dumps(probe(int(sys.argv[-1]))))
 elif '--old' in sys.argv:print('ENTRY_RESULT='+json.dumps(probe(-1,old=True)))
 elif '--chain' in sys.argv:print('ENTRY_RESULT='+json.dumps(chain_probe()))
 else:main()
