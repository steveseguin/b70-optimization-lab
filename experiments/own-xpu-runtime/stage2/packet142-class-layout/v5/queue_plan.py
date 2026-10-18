"""Six new proposals, planned only in disposable queues; never enqueue."""
import json,subprocess,sys,tempfile,shutil
from pathlib import Path
from build_engine import P,LOCAL,ROOT,sha,save,limits
from bracket_config import VALUES
QUEUE=LOCAL.parents[1]/'ops/lane-queue'
def proposal(variant,kind):
 upper=360 if kind=='smoke' else 1200
 return dict(name='packet142-'+variant+'-'+kind+'-B',lane='B',argv=['/usr/bin/python3','-B',str((P/'bracket_job.py').relative_to(ROOT)),'--variant',variant,'--kind',kind,'--lane','B','--output',str(P/'evidence'/('device-'+variant+'-'+('smoke' if kind=='smoke' else 'v5')+'-B')),'--fault-review','{REVIEW}','--authorized-device-window'],env_extra={},review=str((P/'fault_review.py').relative_to(ROOT)),plan=dict(host_required_available_bytes=97*1024**3+1200*1024**2,expected_seconds=[240,upper] if kind=='smoke' else [720,upper],watchdog_seconds=4800))
def main():
 limits();copies=LOCAL/'proposals';copies.mkdir(exist_ok=True);snapshot=LOCAL/'lineage-inputs/queue';snapshot.mkdir(exist_ok=True)
 for src in QUEUE.glob('*.py'):shutil.copy2(src,snapshot/src.name)
 rows=[]
 for variant in VALUES:
  for kind in ('smoke','bracket'):
   name='proposed-p142-'+variant+'-'+('smoke' if kind=='smoke' else 'v5')+'-B.txt';row=proposal(variant,kind);content=json.dumps(row)+'\n'
   assert row['plan']['watchdog_seconds']>=4*row['plan']['expected_seconds'][1]
   live=QUEUE/name
   if live.exists():assert live.read_text()==content,'existing proposal changed'
   else:live.write_text(content)
   (copies/name).write_text(content)
   with tempfile.TemporaryDirectory(prefix='p142-plan-') as d:
    tmp=Path(d)
    for src in snapshot.glob('*.py'):shutil.copy2(src,tmp/src.name)
    (tmp/'queue-B.txt').write_text(content)
    cmd=[sys.executable,'-B',str(QUEUE/'lanequeue.py'),'plan','--lane','B','--directory',str(tmp)]
    log=P/'evidence'/('plan-'+variant+'-'+kind+'.log')
    with log.open('w') as stream:r=subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,timeout=300)
    assert r.returncode==0,log.read_text()[-6000:]
   rows.append(dict(proposal_name=str(live.relative_to(ROOT)),sha256=sha(live),mirror=str((copies/name).relative_to(ROOT)),log=str(log.relative_to(ROOT)),log_sha256=sha(log),unit='screen-'+row['name']+'.service',**row['plan']))
 paths=[P/'queue_plan.py',*copies.glob('*.txt'),*(ROOT/r['log'] for r in rows)]
 save(P/'evidence/queue-plan.json',dict(passed=True,device_executed=False,live_queue_modified=False,queued=False,rows=rows,sources={str(f.relative_to(ROOT)):sha(f) for f in paths}))
if __name__=='__main__':main()
