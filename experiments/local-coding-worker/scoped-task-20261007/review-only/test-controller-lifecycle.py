"""Only temporary fixtures and fake Popen; never call a live endpoint/controller."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
SOURCE=Path('/home/steve/scoped-worker-controller-20261007.py')
spec=importlib.util.spec_from_file_location('controller_review_fixture',SOURCE)
C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)

class LifecycleTests(unittest.TestCase):
 def exercise(self,mode):
  calls={'signals':[],'waits':0,'spawns':0,'healthy':0};running=True
  class Child:
   returncode=None
   def poll(self):
    nonlocal running
    if mode=='complete':running=False;self.returncode=0
    return None if running else self.returncode
   def send_signal(self,signum):
    nonlocal running
    calls['signals'].append(signum);running=False;self.returncode=130
    if mode=='exit-race':raise ProcessLookupError('fixture child exited')
   def wait(self):calls['waits']+=1;return self.returncode
  child=Child()
  def spawn(*a,**k):calls['spawns']+=1;return child
  def healthy():
   calls['healthy']+=1
   if calls['healthy']>=3 and mode in ('fault','exit-race'):raise RuntimeError('fixture server fault')
  def sleeping(n):
   if mode=='monitor-exception':raise ValueError('fixture monitor failure')
  def install(signum,handler):
   if mode=='pre-spawn-interrupt' and signum==C.signal.SIGTERM:handler(signum,None)
  with tempfile.TemporaryDirectory(prefix='controller-offline-') as tmp:
   root=Path(tmp);lane=root/'lane';lane.mkdir();out=root/'out';out.mkdir();server=out/'server';server.mkdir()
   (out/'acceptance').mkdir();(out/'acceptance/worker_action_latency.py').write_text('fixture')
   for name in ('boundaries','transport-canary'):
    (out/name).mkdir();(out/name/'result.json').write_text('{"status":"passed"}')
   (lane/'task.json').write_text('{}');(lane/'worker-profile.json').write_text('{}')
   sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
   plan={'worker':{'code_bindings':{},'profile_sha256':sha(lane/'worker-profile.json')},'task':{'task_sha256':sha(lane/'task.json'),'acceptance_sha256':sha(out/'acceptance/worker_action_latency.py')}}
   (lane/'runtime-plan.json').write_text(json.dumps(plan))
   original=Path.read_text
   def read(p,*a,**k):
    if str(p)=='/proc/meminfo':return 'MemAvailable: 100000000 kB\n'
    return original(p,*a,**k)
   with patch.object(C,'ROOT',root),patch.object(C,'LANE',lane),patch.object(C,'OUT',out),patch.object(C,'SERVER',server),patch.object(C,'source',return_value={'head':'fixture','status':''}),patch.object(C,'supervisor',return_value={'pid':123,'start_ticks':1,'age_s':1}),patch.object(C,'healthy',side_effect=healthy),patch.object(C.subprocess,'Popen',side_effect=spawn),patch.object(C.subprocess,'check_output',side_effect=AssertionError('No host commands allowed')),patch.object(C.time,'sleep',side_effect=sleeping),patch.object(C.signal,'signal',side_effect=install),patch.object(Path,'read_text',read),contextlib.redirect_stdout(io.StringIO()):
    if mode in ('monitor-exception','pre-spawn-interrupt'):
     with self.assertRaises((ValueError,RuntimeError)):C.main()
    else:C.main()
  return calls
 def test_normal_child_exit_waited_without_signal(self):
  c=self.exercise('complete');self.assertEqual((c['spawns'],c['waits'],c['signals']),(1,1,[]))
 def test_fault_interrupts_once_and_waits(self):
  c=self.exercise('fault');self.assertEqual((c['spawns'],c['waits'],len(c['signals'])),(1,1,1))
 def test_unexpected_monitor_error_still_interrupts_and_waits(self):
  c=self.exercise('monitor-exception');self.assertEqual((c['spawns'],c['waits'],len(c['signals'])),(1,1,1))
 def test_child_exit_race_does_not_escape_wait(self):
  c=self.exercise('exit-race');self.assertEqual((c['spawns'],c['waits'],len(c['signals'])),(1,1,1))
 def test_pre_spawn_interrupt_never_creates_child(self):
  c=self.exercise('pre-spawn-interrupt');self.assertEqual((c['spawns'],c['waits'],c['signals']),(0,0,[]))

if __name__=='__main__':unittest.main(verbosity=2)
