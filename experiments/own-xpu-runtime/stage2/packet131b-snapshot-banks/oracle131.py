"""Run the new copy's exact pre-LATE oracle subprocess, without root redirection."""
import json,subprocess
from unittest.mock import patch
from build131 import P,ROOT,sha,save,cpu_main
def main():
 import queue_runner as q
 actual=subprocess.run;calls=[]
 def observe(cmd,**kwargs):
  assert cmd==['nice','-n','19','taskset','-c','8-15,24-31','python3','-B',str(P/'shared_oracle.py'),'--require-complete']
  result=actual(cmd,stdin=subprocess.DEVNULL,timeout=180,**kwargs)
  calls.append(dict(command=cmd,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr));return result
 with patch.object(subprocess,'run',side_effect=observe):assert q.oracle_ready()
 assert (P/'oracle').is_symlink() and (P/'oracle').resolve()==(P.parent/'packet49-integrate/oracle').resolve()
 files=[P/'oracle131.py',P/'queue_runner.py',P/'shared_oracle.py',P/'oracle-binding.json']
 save(P/'evidence/oracle131.json',dict(passed=True,device_executed=False,root_redirected=False,static_binding=__import__('shared_oracle').static_binding(),calls=calls,sources={str(f.relative_to(ROOT)):sha(f) for f in files}))
 print('Packet131 actual queue pre-LATE oracle subprocess PASS')
if __name__=='__main__':cpu_main();main()
