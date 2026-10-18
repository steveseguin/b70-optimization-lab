"""Plan every proposed job on a private queue; never install a live queue."""
import json,subprocess,sys,tempfile
from pathlib import Path
from build_engine import P,ROOT,save,sha,limits
from screen_jobs import jobs,output,WRAPPER,seal_jobs

def main():
 limits();seal_jobs();queue=P.parents[1]/'ops/lane-queue';plans=[]
 review=str((WRAPPER/'fault_review.py').relative_to(ROOT));groups=[]
 for suffix in (81920,122880):
  row=dict(name=f'packet127-micro-{suffix}-B',lane='B',argv=['/usr/bin/python3','-B',str((P/'run_micro.py').relative_to(ROOT)),'--suffix',str(suffix),'--lane','B','--run','--fault-review','{REVIEW}','--authorized-device-window'],env_extra={},review=review)
  groups.append((f'micro-{suffix}-B','B',[row],dict(expected_seconds=100,watchdog_seconds=1200,condition='coordinator admission; independent fresh device micro')))
 for lane in ('B','A'):
  rows=[]
  for i,job in enumerate(jobs(lane,'81920' if lane=='A' else None)):
   rows.append(dict(name=f'packet127-{lane}-{i}',lane=lane,argv=['/usr/bin/python3','-B',str((P/'screen_job.py').relative_to(ROOT)),'--lane',lane,'--index',str(i),'--output',str(output(job)),'--fault-review','{REVIEW}','--authorized-device-window'],env_extra={},review=review))
  groups.append((lane,lane,rows,dict(expected_seconds_per_process=450,expected_total_seconds=450*len(rows),watchdog_seconds_per_process=3600,condition='both exact micros; '+('complete B winner >=0.5% over both controls' if lane=='A' else 'fixed four-process grid'))))
 for label,lane,rows,budget in groups:
  payload=''.join(json.dumps(r)+'\n' for r in rows)
  with tempfile.TemporaryDirectory(prefix='p127-plan-',dir=P/'build/tmp') as tmp:
   dest=Path(tmp)
   for f in queue.glob('*.py'):(dest/f.name).write_bytes(f.read_bytes())
   (dest/f'queue-{lane}.txt').write_text(payload)
   cmd=[sys.executable,'-B',str(queue/'lanequeue.py'),'plan','--lane',lane,'--directory',str(dest)]
   log=P/'evidence'/f'queue-plan-{label}.log'
   with log.open('w') as out:subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,check=True,timeout=480)
  proposal=queue/f'proposed-p127-{label}.txt'
  if proposal.exists():assert proposal.read_text()==payload,'existing proposal differs'
  else:proposal.write_text(payload)
  plans.append(dict(lane=lane,proposal=str(proposal.relative_to(ROOT)),sha256=sha(proposal),command=cmd,log_sha256=sha(log),passed=True,**budget))
  print(label,'temporary queue plan PASS',flush=True)
 save(P/'evidence/queue-plans.json',dict(passed=True,device_executed=False,live_queue_modified=False,plans=plans,scope='durations are planning estimates, not performance claims; normal reservation/drain waits may extend wall time'))
if __name__=='__main__':main()
