"""Write the new micro proposal and run the real planner on a private queue."""
import json, subprocess, sys, tempfile
from pathlib import Path
from build_engine import P, ROOT, limits, sha, save
def main():
 limits();queue=P.parents[1]/'ops/lane-queue'
 proposal=queue/'proposed-p105b-micro-B.txt'
 row=dict(name='packet105b-micro-B',lane='B',argv=['/usr/bin/python3','-B',str((P/'run_micro.py').relative_to(ROOT)),
     '--lane','B','--run','--fault-review','{REVIEW}','--authorized-device-window'],env_extra={},
     review=str((P.parent/'screen/v4-lanes/fault_review.py').relative_to(ROOT)))
 payload=json.dumps(row)+'\n'
 if proposal.exists():assert proposal.read_text()==payload
 else:proposal.write_text(payload)
 with tempfile.TemporaryDirectory(prefix='p105b-micro-',dir=P/'build/tmp') as tmp:
  dest=Path(tmp)
  for source in queue.glob('*.py'):(dest/source.name).write_bytes(source.read_bytes())
  (dest/'queue-B.txt').write_text(payload)
  cmd=[sys.executable,'-B',str(queue/'lanequeue.py'),'plan','--lane','B','--directory',str(dest)]
  log=P/'evidence/micro-queue-plan.log'
  with log.open('w') as out:subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,check=True,timeout=240)
 save(P/'evidence/micro-queue-plan.json',dict(passed=True,device_executed=False,live_queue_modified=False,
      proposal=str(proposal.relative_to(ROOT)),proposal_sha256=sha(proposal),command=cmd,log_sha256=sha(log)))
 print('micro proposal planned on private queue',flush=True)
if __name__=='__main__':main()
