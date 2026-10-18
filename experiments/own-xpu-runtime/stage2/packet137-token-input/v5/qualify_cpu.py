"""One serial CPU qualification pass. Stop on the first failed gate; never retry."""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
from build_engine import P,ROOT,limits
STEPS=[
 ('build',P/'build_engine.py',[]),
 ('target',P.parent/'target_gate.py',[]),
 ('full-shape',P/'full_shape.py',[]),
 ('reset-bytes',P/'reset_gate.py',[]),
 ('protocol',P/'protocol_gate.py',[]),
 ('state-regression',P/'state_regression.py',[]),
 ('exec-limits',P/'exec_gate.py',[]),
 ('policy',P/'test_v5.py',[]),
 ('safety',P/'safety_gate.py',[]),
 ('cpu-seal',P/'cpu_seal.py',['--seal']),
 ('argument',P/'argument_gate.py',[]),
 ('legacy-windows',P/'legacy_window_gate.py',[]),
 ('all-windows',P/'all_window_gate.py',[]),
 ('worker',P/'worker_gate.py',[]),
 ('launch-limits',P/'launch_limit_gate.py',[]),
 ('queue-plan',P/'queue_plan.py',[]),
 ('queue-gate',P/'queue_gate.py',[]),
 ('qualification',P/'readiness.py',['--seal'])]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--start',choices=[s[0] for s in STEPS],default='build');a=ap.parse_args()
 limits();assert os.environ.get('OMP_NUM_THREADS')=='2'
 # Keep native launch-limit probes unlimited. Heavy CPU children apply their
 # own 4 GiB cap in __main__; this small coordinator never allocates payloads.
 import resource
 assert resource.getrlimit(resource.RLIMIT_AS)==(-1,-1)
 start=next(i for i,s in enumerate(STEPS) if s[0]==a.start)
 for name,script,args in STEPS[start:]:
  limits();log=P/'evidence'/('qualify-'+name+'.log')
  print('START '+name,flush=True);began=time.monotonic()
  with log.open('w') as f:
   result=subprocess.run([sys.executable,'-B',str(script),*args],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=4500)
  print(json.dumps(dict(stage=name,returncode=result.returncode,seconds=time.monotonic()-began)),flush=True)
  if result.returncode:raise SystemExit(result.returncode)
  limits()
if __name__=='__main__':main()
