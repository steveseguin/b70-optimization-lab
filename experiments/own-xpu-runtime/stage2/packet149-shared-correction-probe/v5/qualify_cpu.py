"""Reproducible serial CPU qualification. Stops at the first refusal."""
import argparse,subprocess,sys,resource
from p149_v5_build_engine import P,LOCAL,ROOT,limits
STEPS=[('build',P/'p149_v5_build_engine.py',[]),('shape',P/'p149_v5_full_shape.py',[]),('bytes',P/'byte_gate.py',[]),('limits',P/'exec_gate.py',[]),('safety',P/'safety_gate.py',[]),('admission',P/'admission_gate.py',[]),('stage-proposals',P/'p149_v5_queue_plan.py',['--stage']),('seal',P/'cpu_seal.py',['--seal']),('entry',P/'entry_gate.py',[]),('launch-limits',P/'launch_limit_gate.py',[]),('worker',P/'worker_gate.py',[]),('report',P/'report_gate.py',[]),('queue',P/'p149_v5_queue_plan.py',[]),('pins',P/'pin_gate.py',[])]
def main():
 assert resource.getrlimit(resource.RLIMIT_AS)==(-1,-1)
 ap=argparse.ArgumentParser();ap.add_argument('--start',choices=[r[0] for r in STEPS],default='build');a=ap.parse_args()
 for name,path,args in STEPS[next(i for i,r in enumerate(STEPS) if r[0]==a.start):]:
  limits();print('START',name,flush=True)
  with (P/'evidence'/('qualify-'+name+'.log')).open('w') as log:
   r=subprocess.run([sys.executable,'-B',str(path),*args],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=4500,cwd=ROOT)
  if r.returncode:raise SystemExit(r.returncode)
  if name=='build':
   for mode in ('gnu-host','device'):(P/'build'/mode/'entry-main.o').unlink(missing_ok=True)
  print('PASS',name,flush=True)
if __name__=='__main__':main()
