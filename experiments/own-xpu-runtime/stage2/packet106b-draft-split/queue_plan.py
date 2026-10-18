"""New proposals only; plan on temporary queue copies with no devices."""
import json,subprocess,sys,tempfile
from pathlib import Path
from build_engine import P,ROOT,save,sha,limits
from screen_jobs import jobs,confirm_jobs,output,WRAPPER,seal_jobs,smoke_output
def main():
 limits();seal_jobs();queue=P.parents[1]/'ops/lane-queue';rows=[]
 def entry(name,lane,script,args):
  return dict(name=name,lane=lane,argv=['/usr/bin/python3','-B',str((P/script).relative_to(ROOT)),*args,'--fault-review','{REVIEW}','--authorized-device-window'],env_extra={},review=str((WRAPPER/'fault_review.py').relative_to(ROOT)))
 proposals=[('B','proposed-p106b-smoke-B.txt',[entry('packet106b-B-smoke','B','smoke_job.py',['--output',str(smoke_output())])])]
 for lane in ('B',):
  proposals.append((lane,f'proposed-p105b-{lane}-grid.txt',[entry(f'packet106b-{lane}-grid-{r["index"]}',lane,'screen_job.py',['--lane',lane,'--index',str(r['index']),'--output',str(output(r))]) for r in jobs(lane)]))
 proposals.append(('A','proposed-p105b-A-confirm.txt',[entry(f'packet106b-A-confirm-{r["index"]}','A','confirm_job.py',['--index',str(r['index']),'--output',str(output(r))]) for r in confirm_jobs()]))
 with tempfile.TemporaryDirectory(prefix='p106b-queue-',dir=P/'build/tmp') as tmp:
  dest=Path(tmp)
  for source in queue.glob('*.py'):(dest/source.name).write_bytes(source.read_bytes())
  for lane,name,entries in proposals:
   proposal=queue/name;payload=''.join(json.dumps(r)+'\n' for r in entries)
   if proposal.exists():assert proposal.read_text()==payload,'never overwrite a different proposal'
   else:proposal.write_text(payload)
   (dest/f'queue-{lane}.txt').write_text(payload)
   cmd=[sys.executable,'-B',str(queue/'lanequeue.py'),'plan','--lane',lane,'--directory',str(dest)]
   log=P/'evidence'/(name+'.plan.log')
   with log.open('w') as f:subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=240)
   rows.append(dict(lane=lane,proposal=str(proposal.relative_to(ROOT)),proposal_sha256=sha(proposal),jobs=len(entries),command=cmd,passed=True,log_sha256=sha(log)))
 save(P/'evidence/queue-plans.json',dict(passed=True,device_executed=False,live_queue_modified=False,plans=rows,record_lane='A'))
 print('Small B smoke, four-run B grid and conditional A confirmation planned on temporary queues.')
if __name__=='__main__':main()
