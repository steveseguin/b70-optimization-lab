"""New proposals only; validate in a disposable copy of the queue tools."""
import json,subprocess,sys,tempfile
from pathlib import Path
from build_engine import P,ROOT,save,sha,limits
from screen_jobs import jobs,output,WRAPPER,seal_jobs
def main():
    limits();seal_jobs();queue=P.parents[1]/'ops/lane-queue';rows=[]
    with tempfile.TemporaryDirectory(prefix='p101-queue-',dir=P/'build/tmp') as tmp:
        dest=Path(tmp)
        for source in queue.glob('*.py'):(dest/source.name).write_bytes(source.read_bytes())
        for lane in ('B','A'):
            proposal=queue/f'proposed-p101-{lane}-grid.txt'
            entries=[dict(name=f'packet101-{lane}-grid-{row["index"]}',lane=lane,
                  argv=['/usr/bin/python3','-B',str((P/'screen_job.py').relative_to(ROOT)),
                    '--lane',lane,'--index',str(row['index']),'--output',str(output(row)),
                    '--fault-review','{REVIEW}','--authorized-device-window'],env_extra={},
                  review=str((WRAPPER/'fault_review.py').relative_to(ROOT))) for row in jobs(lane)]
            payload=''.join(json.dumps(r)+'\n' for r in entries)
            if proposal.exists():assert proposal.read_text()==payload,'never overwrite a different proposal'
            else:proposal.write_text(payload)
            (dest/f'queue-{lane}.txt').write_bytes(proposal.read_bytes())
            cmd=[sys.executable,'-B',str(queue/'lanequeue.py'),'plan','--lane',lane,'--directory',str(dest)]
            log=P/'evidence'/f'queue-plan-{lane}.log'
            with log.open('w') as f:subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=240)
            rows.append(dict(lane=lane,proposal=str(proposal.relative_to(ROOT)),proposal_sha256=sha(proposal),command=cmd,passed=True,log_sha256=sha(log)))
    save(P/'evidence/queue-plans.json',dict(passed=True,device_executed=False,live_queue_modified=False,plans=rows,record_lane='A'))
    print('Six jobs planned in temporary queues; records remain lane A.')
if __name__=='__main__':main()
