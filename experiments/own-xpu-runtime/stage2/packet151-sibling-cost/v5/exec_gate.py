import freeze_safe
freeze_safe.install()
"""CPU interception of real pre-exec limit guards; no native process starts."""
import json,resource,subprocess,sys
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parent

def main():
 from p151_v5_build_engine import limits,save,sha
 import p151_v5_exec_limits as exec_limits
 # The normal CLI arrives with unlimited AS. Intercept the final Popen after
 # the real guard checks its complete census, without opening any native owner.
 assert resource.getrlimit(resource.RLIMIT_AS)==(-1,-1)
 baseline=exec_limits.snapshot();called=[]
 with patch.object(subprocess,'Popen',side_effect=lambda *a,**k:called.append(a)):
  exec_limits.install()
  subprocess.Popen(['/never-executed/build/own-rt-iq3','--device'])
  assert len(called)==1
  with patch.object(exec_limits,'snapshot',return_value=dict(baseline,changed=[1,2])):
   try:subprocess.Popen(['/never-executed/build/own-rt-iq3','--device'])
   except AssertionError as e:assert 'changed before native exec' in str(e)
   else:raise AssertionError('changed resource limit accepted')
  assert len(called)==1
 limits()
 # Now test the actual bad inherited-cap boundary in a fresh CPU process.
 code=r'''
import json,subprocess,sys,resource
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
from unittest.mock import patch
sys.path.insert(0,sys.argv[1])
import p151_v5_exec_limits as exec_limits
called=[]
with patch.object(subprocess,'Popen',side_effect=lambda *a,**k:called.append(a)):
 exec_limits.install()
 try:subprocess.Popen(['/never-executed/build/own-rt-iq3','--device'])
 except AssertionError as e:assert 'finite RLIMIT_AS' in str(e)
 else:raise AssertionError('inherited CPU cap accepted')
 assert not called
print(json.dumps(dict(passed=True,device_executed=False,capped_launch_refused=True,actual_native_launches=0)))
'''
 row=freeze_safe.run([sys.executable,'-B','-c',code,str(P)],stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True,timeout=30)
 result=json.loads(row.stdout)
 result.update(unchanged_unlimited_launch_intercepted=True,changed_limit_refused=True,unlimited_rlimit_census=baseline)
 result['sources']={str(f.relative_to(P.parents[4])):sha(f) for f in (P/'exec_gate.py',P/'p151_v5_exec_limits.py',P/'screen.py',P/'tp2_worker.py')}
 save(P/'evidence/exec-limits.json',result);print('pre-exec limit gate PASS')
if __name__=='__main__':main()
