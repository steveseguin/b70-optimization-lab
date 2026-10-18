"""Actual wrapper admission, closed worker imports and packet winner rules."""
import subprocess,sys
from build_engine import P,ROOT,sha,save,limits
from screen_jobs import WRAPPER
def main():
 limits();tests=['test_reporting','test_refusal','test_lane_admission','test_plan_admission','test_placement','test_chain_patch']
 commands=[([sys.executable,'-B','-m','unittest',*tests,'-v'],WRAPPER),([sys.executable,'-B','-m','unittest','test_screen','test_micro_gate','test_micro_runner','test_consumers','-v'],P)]
 for i,(cmd,cwd) in enumerate(commands):
  with (P/'evidence'/f'python-tests-{i}.log').open('w') as log:subprocess.run(cmd,cwd=cwd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
 sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'python_gate.py',P/'test_screen.py',P/'test_micro_gate.py',P/'test_micro_runner.py',P/'test_consumers.py',P/'memory_plans.py',P/'memory_gate.py',P/'bundle_selection.py',*[P.parent/'packet84-record-bundle'/n for n in ('merge_dispatch.py','packet56_submission.py','p49d_k2.py','selection_gate.py','bundle_selection.py')],*[WRAPPER/(t+'.py') for t in tests]]}
 save(P/'evidence/python-tests.json',dict(passed=True,device_executed=False,sources=sources,commands=[dict(argv=c,cwd=str(d)) for c,d in commands]))
 print('shared admission, worker import, placement and packet tests PASS')
if __name__=='__main__':main()
