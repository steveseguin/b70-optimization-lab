"""Plan the one proposal on a temporary queue only; never enqueue."""
import json,resource,subprocess,sys,tempfile
from pathlib import Path
from build_engine import P,ROOT,limits,sha,save

def main():
 limits();queue=P.parents[1]/'ops/lane-queue';proposal=queue/'proposed-p141-probe-B.txt'
 with tempfile.TemporaryDirectory(prefix='p141-plan-') as d:
  dest=Path(d);(dest/'queue-B.txt').write_bytes(proposal.read_bytes())
  cmd=[sys.executable,'-B',str(queue/'lanequeue.py'),'plan','--lane','B','--directory',str(dest)]
  with (P/'evidence/queue-plan.log').open('w') as log:
   subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
 save(P/'evidence/queue-plans.json',dict(passed=True,device_executed=False,live_queue_changed=False,proposal=str((P/'proposal.snapshot.txt').relative_to(ROOT)),coordinator_proposal=str(proposal.relative_to(ROOT)),proposal_sha256=sha(proposal),expected_seconds=[600,1200],watchdog_seconds=4800,unit='screen-packet141b-probe-B.service'))
 print('temporary lane-B queue plan PASS; not queued')
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
