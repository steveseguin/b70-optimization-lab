"""Plan two proposed jobs on a temporary queue, then write only new proposal file."""
import json,subprocess,tempfile
from pathlib import Path
from build_engine import P,ROOT,limits,save,sha

def main():
 limits();queue=ROOT/'experiments/own-xpu-runtime/ops/lane-queue'
 rows=[]
 for owner in ('1','2'):
  rows.append(dict(name='packet116-micro-B-'+owner,lane='B',argv=['/usr/bin/python3','-B',str((P/'run_micro.py').relative_to(ROOT)),'--lane','B','--owner',owner,'--run','--fault-review','{REVIEW}','--authorized-device-window'],env_extra={},review='experiments/own-xpu-runtime/stage2/screen/v4-lanes/fault_review.py'))
 contents=''.join(json.dumps(r,separators=(',',':'))+'\n' for r in rows)
 with tempfile.TemporaryDirectory(prefix='ownrt-p116-micro-plan-') as temp:
  target=Path(temp)/'queue-B.txt';target.write_text(contents)
  cmd=['/usr/bin/python3','-B',str(queue/'lanequeue.py'),'plan','--lane','B','--directory',temp]
  result=subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=180)
  (P/'evidence/queue-plan.log').write_text(result.stdout)
  assert result.returncode==0,result.stdout
  plans=[json.loads(line) for line in result.stdout.splitlines()];assert len(plans)==2 and all(r['plan']=='passed' for r in plans),plans
 proposal=queue/'proposed-p116-micro-B.txt';proposal.write_text(contents)
 save(P/'evidence/queue-plan.json',dict(passed=True,device_executed=False,temporary_queue=True,live_queue_modified=False,proposal=str(proposal.relative_to(ROOT)),proposal_sha256=sha(proposal),plans=plans,expected_seconds_per_owner=240,watchdog_seconds_per_owner=1200))
 print('two proposed micro jobs compiled, sealed and CPU-planned; no live queue changed',flush=True)
if __name__=='__main__':main()
