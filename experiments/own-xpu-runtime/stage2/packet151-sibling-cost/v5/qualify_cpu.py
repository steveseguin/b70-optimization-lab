"""Serial CPU-only predevice qualification of the existing pinned build.

No GGUF/full-shape reads and no native device execution. Build and paired
arithmetic proofs must already match. This runner never writes final readiness.
"""
import argparse,json,resource,subprocess,sys
import freeze_safe
freeze_safe.install()
from p151_v5_build_engine import P,LOCAL,ROOT,limits
STEPS=[('analysis',P/'analysis_gate.py',[]),('state',P/'state_gate.py',[]),
 ('aux',P/'aux_gates.py',[]),('limits',P/'exec_gate.py',[]),
 ('safety',P/'safety_gate.py',[]),('admission',P/'admission_gate.py',[]),
 ('stage-proposals',P/'p151_v5_queue_plan.py',['--stage']),
 ('seal',P/'cpu_seal.py',['--seal']),('entry',P/'entry_gate.py',[]),
 ('launch-limits',P/'launch_limit_gate.py',[]),('worker',P/'worker_gate.py',[]),
 ('report',P/'report_gate.py',[]),('queue',P/'p151_v5_queue_plan.py',[]),
 ('pins',P/'pin_gate.py',[])]
def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--start',choices=[r[0] for r in STEPS],default='analysis');a=ap.parse_args()
 assert not (LOCAL/'READY-FOR-DEVICE.json').exists(),'invalidate readiness before preparing again'
 assert resource.getrlimit(resource.RLIMIT_AS)==(-1,-1)
 resource.setrlimit(resource.RLIMIT_DATA,(4*1024**3,)*2)
 from cpu_seal import check_sources
 for name in ('build','pair-cpu'):
  proof=json.loads((P/'evidence'/(name+'.json')).read_text())
  assert proof['passed'] and not proof['device_executed']
  check_sources(proof['sources']);check_sources(proof.get('artifacts',{}))
 for name,path,args in STEPS[next(i for i,r in enumerate(STEPS) if r[0]==a.start):]:
  limits();print('START',name,flush=True)
  with (P/'evidence'/('qualify-'+name+'.log')).open('w') as log:
   r=freeze_safe.run([sys.executable,'-B',str(path),*args],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=4500,cwd=ROOT)
  if r.returncode:raise SystemExit(r.returncode)
  print('PASS',name,flush=True)
if __name__=='__main__':main()
