"""Plan proposals on private temporary queues before writing new proposal files."""
import json,subprocess,sys,tempfile
from pathlib import Path
from build_engine import P,ROOT,save,sha,limits
from screen_jobs import jobs,output,WRAPPER,seal_jobs

def main():
 limits();seal_jobs();queue=P.parents[1]/'ops/lane-queue';rows=[]
 for lane in ('B','A'):
  payload=''.join(json.dumps(dict(name=f'packet120-{lane}-{i}',lane=lane,argv=['/usr/bin/python3','-B',str((P/'screen_job.py').relative_to(ROOT)),'--lane',lane,'--index',str(i),'--output',str(output(job)),'--fault-review','{REVIEW}','--authorized-device-window'],env_extra={},review=str((WRAPPER/'fault_review.py').relative_to(ROOT))))+'\n' for i,job in enumerate(jobs(lane)))
  with tempfile.TemporaryDirectory(prefix='p120-plan-',dir=P/'build/tmp') as tmp:
   dest=Path(tmp)
   for f in queue.glob('*.py'):(dest/f.name).write_bytes(f.read_bytes())
   (dest/f'queue-{lane}.txt').write_text(payload)
   cmd=[sys.executable,'-B',str(queue/'lanequeue.py'),'plan','--lane',lane,'--directory',str(dest)]
   log=P/'evidence'/f'queue-plan-{lane}.log'
   with log.open('w') as out:subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,check=True,timeout=240)
  proposal=queue/f'proposed-p120-{lane}.txt'
  if proposal.exists():assert proposal.read_text()==payload,'existing proposal differs'
  else:proposal.write_text(payload)
  rows.append(dict(lane=lane,proposal=str(proposal.relative_to(ROOT)),sha256=sha(proposal),command=cmd,log_sha256=sha(log),passed=True,conditional_on_B_win=lane=='A'))
 save(P/'evidence/queue-plans.json',dict(passed=True,device_executed=False,live_queue_modified=False,plans=rows))
 print('Both three-process brackets planned on private queues',flush=True)
if __name__=='__main__':main()
