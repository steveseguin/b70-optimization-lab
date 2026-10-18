"""No kernels: validate protocol, evidence and a temporary queue plan."""
import json,subprocess,sys,tempfile
from pathlib import Path
from build_engine import P,ROOT,limits,save,sha
def main():
 limits()
 from route_inputs import require_ready
 routes=require_ready()
 commands=[('protocol-tests',[sys.executable,'-B','-m','unittest','test_micro_gate','-v']),
           ('micro-plan',[sys.executable,'-B',str(P/'run_micro.py'),'--lane','B','--plan'])]
 results=[]
 for name,cmd in commands:
  with (P/'evidence'/(name+'.log')).open('w') as f:subprocess.run(cmd,cwd=P,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
  results.append(dict(name=name,command=cmd,passed=True))
 queue=P.parents[1]/'ops/lane-queue';proposal=queue/'proposed-p104-micro-B.txt'
 with tempfile.TemporaryDirectory(prefix='p104-queue-plan-') as tmp:
  (Path(tmp)/'queue-B.txt').write_bytes(proposal.read_bytes())
  cmd=[sys.executable,'-B',str(queue/'lanequeue.py'),'plan','--lane','B','--directory',tmp]
  with (P/'evidence/queue-plan.log').open('w') as f:subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
  results.append(dict(name='temporary-queue-plan',command=cmd,passed=True))
 save(P/'evidence/preparation-checks.json',dict(passed=True,device_executed=False,live_queue_modified=False,long_cpu_gates_run=False,route_vectors=routes['micro_route_vectors'],proposal_sha256=sha(proposal),build_receipt_sha256=sha(P/'evidence/microbench-build.json'),checks=results))
 print('13 protocol checks, real routes, micro plan, temporary queue plan PASS; no kernels')
if __name__=='__main__':main()
