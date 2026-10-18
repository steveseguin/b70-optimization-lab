"""Exercise original shared admission/report/drain code with CPU mocks only."""
import json,subprocess,sys
from pathlib import Path
from build_engine import P,ROOT,sha,save,limits
from screen_jobs import WRAPPER
def main():
 limits();tests=['test_reporting','test_refusal','test_lane_admission','test_plan_admission']
 commands=[([sys.executable,'-B','-m','unittest',*tests,'-v'],WRAPPER),
           ([sys.executable,'-B','-m','unittest','test_attribute','test_screen','-v'],P)]
 for i,(cmd,cwd) in enumerate(commands):
  with (P/'evidence'/f'python-tests-{i}.log').open('w') as log:
   subprocess.run(cmd,cwd=cwd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
 sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'python_gate.py',P/'test_attribute.py',P/'test_screen.py',*[WRAPPER/(t+'.py') for t in tests]]}
 save(P/'evidence/python-tests.json',dict(passed=True,device_executed=False,cpu_model_executed=False,sources=sources,commands=[dict(argv=c,cwd=str(d)) for c,d in commands]))
 print('shared real admission/report/drain mocks and packet tests PASS')
if __name__=='__main__':main()
