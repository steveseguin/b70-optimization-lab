"""Ship the twelve-prompt target-only smoke as soon as its view is CPU-ready."""
import json,subprocess,sys,tempfile
from pathlib import Path
from build_engine import P,ROOT,sha,save,limits
from screen_jobs import seal_jobs,smoke_output,WRAPPER
def main():
 limits();seal_jobs();queue=P.parents[1]/'ops/lane-queue';proposal=queue/'proposed-p118-smoke-B.txt'
 row=dict(name='packet118-smoke12-B',lane='B',argv=['/usr/bin/python3','-B',str((P/'smoke_job.py').relative_to(ROOT)),
     '--output',str(smoke_output()),'--fault-review','{REVIEW}','--authorized-device-window'],env_extra={},review=str((WRAPPER/'fault_review.py').relative_to(ROOT)))
 payload=json.dumps(row)+'\n'
 with tempfile.TemporaryDirectory(prefix='p118-smoke-',dir=P/'build/tmp') as tmp:
  dest=Path(tmp)
  for source in queue.glob('*.py'):(dest/source.name).write_bytes(source.read_bytes())
  (dest/'queue-B.txt').write_text(payload)
  cmd=[sys.executable,'-B',str(queue/'lanequeue.py'),'plan','--lane','B','--directory',str(dest)]
  log=P/'evidence/smoke-queue-plan.log'
  with log.open('w') as out:subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,check=True,timeout=240)
 proposal.write_text(payload)
 save(P/'evidence/smoke-queue-plan.json',dict(passed=True,device_executed=False,live_queue_modified=False,
      proposal=str(proposal.relative_to(ROOT)),proposal_sha256=sha(proposal),command=cmd,log_sha256=sha(log),request_count=12,tokens=64))
 print('Twelve-prompt smoke planned on private queue',flush=True)
if __name__=='__main__':main()
