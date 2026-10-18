"""Write proposals and plan only in a temporary copy of the queue directory."""
import json,subprocess,sys,tempfile
from pathlib import Path
from build_engine import P,ROOT,save,sha,limits
from screen_jobs import jobs,output,WRAPPER,seal_jobs

def proposals():
 queue=P.parents[1]/'ops/lane-queue';paths=[]
 for lane,mode,suffix in (('A','grid','A'),('B','confirm','B'),('B','grid','B-grid')):
  result=[]
  for row in jobs(lane,mode=mode):
   dest=output(row) if mode=='grid' else WRAPPER/'evidence'/f'p91-{lane}-confirm-{row["index"]}'
   result.append(dict(name=f'packet91-{lane}-{mode}-{row["index"]}',lane=lane,argv=['/usr/bin/python3','-B',str((P/'screen_job.py').relative_to(ROOT)),'--lane',lane,'--mode',mode,'--index',str(row['index']),'--output',str(dest),'--fault-review','{REVIEW}','--authorized-device-window'],env_extra={},review=str((WRAPPER/'fault_review.py').relative_to(ROOT))))
  path=queue/f'proposed-p91-{suffix}.txt';path.write_text(''.join(json.dumps(r)+'\n' for r in result));paths.append((lane,mode,path))
 return paths

def main():
 limits();seal_jobs();queue=P.parents[1]/'ops/lane-queue';rows=[]
 with tempfile.TemporaryDirectory(prefix='p91-queue-',dir=P/'build/tmp') as tmp:
  dest=Path(tmp)
  # Copy the queue's Python tools and data needed by planning; never live locks,
  # state, pending jobs or review records.
  for source in queue.glob('*.py'):(dest/source.name).write_bytes(source.read_bytes())
  for lane,mode,source in proposals():
   (dest/f'queue-{lane}.txt').write_bytes(source.read_bytes())
   command=[sys.executable,'-B',str(queue/'lanequeue.py'),'plan','--lane',lane,'--directory',str(dest)]
   log=P/'evidence'/f'queue-plan-{lane}-{mode}.log'
   with log.open('w') as f:subprocess.run(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=240)
   rows.append(dict(lane=lane,mode=mode,proposal=str(source.relative_to(ROOT)),sha256=sha(source),command=command,passed=True,log_sha256=sha(log)))
 save(P/'evidence/queue-plans.json',dict(passed=True,device_executed=False,live_queue_modified=False,plans=rows))
 print('13 jobs planned on temporary queues; live queue untouched')
if __name__=='__main__':main()
