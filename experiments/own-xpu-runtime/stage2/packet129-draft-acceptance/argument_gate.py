"""Execute the real worker to both intercepted native argv; no device exec.

Follows packet124b's argument_gate.py: real parser/selection/oracle/placement,
synthetic operational monitor, temporary writes, hard native-exec interception.
"""
import contextlib,importlib.util,json,os,resource,shutil,subprocess,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from build_engine import P,ROOT,sha,save,limits
class Reached(BaseException):pass
class Forbidden(BaseException):pass

def probe():
 from run_screen import VIEW
 from common import sealed
 identity=sealed(SimpleNamespace(lineage=VIEW,seal=VIEW/'screen-seal.json',binary=None,dispatch=None,profile='tp2',timing='token',placement='1'))
 identity['lane']='B'
 import worker
 with tempfile.TemporaryDirectory(prefix='p128-argv-') as directory:
  tmp=Path(directory)
  def audit(event,values):
   if event=='open' and isinstance(values[0],(str,bytes)):
    path=Path(os.fsdecode(values[0])).absolute()
    if str(path).startswith('/dev/dri/'):raise Forbidden('device open forbidden')
    if (values[2] or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND) and path!=Path('/dev/null') and not path.resolve().is_relative_to(tmp):raise Forbidden('write outside CPU scratch: '+str(path))
   if event in ('subprocess.Popen','os.system','os.exec','os.posix_spawn'):raise Forbidden('execution forbidden')
  sys.addaudithook(audit);observations=[]
  def capture(cmd,*a,**kw):
   observations.append(list(map(str,cmd)))
   if len(observations)==2:raise Reached()
   return SimpleNamespace(pid=900001,poll=lambda:None)
  monitor=SimpleNamespace(poll=lambda **k:None,register=lambda pid:None)
  from devices import masked_environment
  spec=importlib.util.spec_from_file_location("p128_queue",P.parents[1]/"ops/lane-queue/lanequeue.py");q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q);ldp=q.library_path()
  with patch.object(subprocess,'Popen',side_effect=capture),patch.object(worker,'DeviceMonitor',return_value=monitor),patch.object(worker,'masked_environment',side_effect=lambda lane,*a,**k:masked_environment(lane,{'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2','LD_LIBRARY_PATH':ldp})):
   try:worker.run(identity,tmp/'run',7200)
   except Reached:pass
  assert len(observations)==2
  for rank,cmd in enumerate(observations):
   for key,value in [('--rank',str(rank)),('--timing','token'),('--max-new','128'),('--seconds','7200'),('--selection-sha256',sha(VIEW/'selection.json')),('--draft-rank','1'),('--target-split','0'),('--context','4096'),('--retain-steps','none')]:assert cmd[cmd.index(key)+1]==value,(key,cmd)
   assert ('--acceptance-shadow' in cmd)==(rank==1)
   assert '--authorized-device-window' in cmd and '--mini' not in cmd
  return dict(passed=True,device_executed=False,native_exec_intercepted=True,argv=observations,operational_admission_synthetic=True)

def main():
 if '--probe' in sys.argv:
  print('ARGUMENT_RESULT='+json.dumps(probe()));return
 limits()
 r=subprocess.run([sys.executable,'-B',str(P/'argument_gate.py'),'--probe'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
 (P/'evidence/argument-gate.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr
 result=json.loads(next(s.removeprefix('ARGUMENT_RESULT=') for s in r.stdout.splitlines() if s.startswith('ARGUMENT_RESULT=')))
 # Use the real native parser with a host-only, payload-only startup backend.
 # The CPU fixture never loads model weights or contacts devices.
 import startup103
 generated,commands=startup103.build();startup=[]
 for rank,cmd in enumerate(result['argv']):
  cmd=cmd[cmd.index(str(P/'selections/acceptance/build/device/own-rt-iq3')):]
  with tempfile.TemporaryDirectory(prefix='p128-native-argv-') as d:
   cmd[cmd.index('--output')+1]=str(Path(d)/'rank')
   # Native priority is operationally synthetic in this nice19 CPU fixture.
   cmd[cmd.index('--native-nice')+1]='19'
   cmd[cmd.index('--selection')+1]=str(P/'selections/acceptance/selection.json')
   # input snapshot paths have left scratch: rebind to the same pinned originals.
   from bootstrap import install
   install()
   from common import D
   inputs=ROOT/D.oracle_inputs()['prompts'][0]['input_bundle']
   for key,leaf in [('--plan','plan.tsv'),('--identity','identity.tsv')]:cmd[cmd.index(key)+1]=str(inputs/leaf)
   startup.append(startup103.native(cmd))
 result.update(startup=startup,build_commands=commands,sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'argument_gate.py',P/'worker.py',P/'run_screen.py',P/'screen129.py',P/'selection.json',P/'startup103.py',P/'teardown.py',P/'analyze.py',*generated]})
 save(P/'evidence/argument-gate.json',result);print('both real worker argv and native startup parsers PASS')
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));main()
