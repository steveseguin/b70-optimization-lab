"""Serial CPU preparation driver. Never launches devices or edits live queues."""
import resource,subprocess,sys
from p183_v5_build_engine import P,ROOT,limits
STEPS=[('build','p183_v5_build_engine.py',[]),('s1-bytes','s1_byte_gate.py',[]),('real-census','real_census_gate.py',[]),('full-shape','p183_v5_full_shape.py',[]),('expected-gain','price_s1.py',[]),('controller','controller_gate.py',[]),('switch','switch_gate.py',[]),('admission','admission_gate.py',[]),('analysis','analysis_gate.py',[]),('submission','submission_rehearsal.py',[]),('safety','safety_gate.py',[]),('limits','exec_gate.py',[]),('loader','loader_gate.py',[]),('stage-proposals','p183_v5_queue_plan.py',['--stage']),('seal','cpu_seal.py',['--seal']),('entry','entry_gate.py',[]),('launch-limits','launch_limit_gate.py',[]),('worker','worker_gate.py',[]),('report','report_gate.py',[]),('queue','p183_v5_queue_plan.py',[]),('pins','pin_gate.py',[])]
def main():
 import argparse
 assert resource.getrlimit(resource.RLIMIT_AS)==(-1,-1)
 ap=argparse.ArgumentParser();ap.add_argument('--start',choices=[x[0] for x in STEPS],default='build');a=ap.parse_args()
 for name,leaf,args in STEPS[next(i for i,x in enumerate(STEPS) if x[0]==a.start):]:
  limits();print('START',name,flush=True)
  with (P/'evidence'/('qualify-'+name+'.log')).open('w') as log:r=subprocess.run([sys.executable,'-B',str(P/leaf),*args],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=3000)
  assert r.returncode==0,name
  print('PASS',name,flush=True)
if __name__=='__main__':main()
