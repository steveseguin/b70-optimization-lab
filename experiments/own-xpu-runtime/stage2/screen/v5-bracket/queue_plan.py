"""Write only proposed queue files; run the real planner in a temporary copy."""
import json,subprocess,sys,tempfile
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits

QUEUE=P.parents[2]/'ops/lane-queue'

def proposals():
    rows=[]
    for kind in ('smoke','bracket'):
        output=P/'evidence'/('p98-'+kind+'-B')
        row=dict(name='packet98-'+kind+'-B',lane='B',
             argv=['/usr/bin/python3','-B',str((P/'bracket_job.py').relative_to(ROOT)),
                   '--kind',kind,'--lane','B','--output',str(output),
                   '--fault-review','{REVIEW}','--authorized-device-window'],
             env_extra={},review=str((P/'fault_review.py').relative_to(ROOT)))
        path=QUEUE/('proposed-p98-'+kind+'-B.txt')
        # Never replace an existing, changed proposal from another task.
        content=json.dumps(row)+'\n'
        if path.exists():assert path.read_text()==content,'proposal already exists with different bytes'
        else:path.write_text(content)
        rows.append((kind,path))
    return rows

def main():
    limits();rows=[]
    with tempfile.TemporaryDirectory(prefix='p98-queue-',dir=B) as tmp:
        dest=Path(tmp)
        for source in QUEUE.glob('*.py'):(dest/source.name).write_bytes(source.read_bytes())
        for kind,source in proposals():
            (dest/'queue-B.txt').write_bytes(source.read_bytes())
            cmd=[sys.executable,'-B',str(QUEUE/'lanequeue.py'),'plan','--lane','B','--directory',str(dest)]
            log=P/'evidence'/('queue-plan-'+kind+'.log')
            with log.open('w') as f:
                subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=240)
            rows.append(dict(kind=kind,proposal=str(source.relative_to(ROOT)),sha256=sha(source),
                             command=cmd,log_sha256=sha(log),passed=True))
    save(P/'evidence/queue-plans.json',dict(passed=True,device_executed=False,live_queue_modified=False,plans=rows))
    print('both lane-B proposals planned in a temporary queue; no live queue edits')
if __name__=='__main__':main()
