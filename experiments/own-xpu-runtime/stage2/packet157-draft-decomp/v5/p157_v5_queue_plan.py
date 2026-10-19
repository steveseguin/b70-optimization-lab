"""Both lanes, A first; all plans run on temporary queues, never live queues."""
import argparse,json,subprocess,sys,tempfile,shutil
from pathlib import Path
from p157_v5_build_engine import P,LOCAL,ROOT,sha,save,limits
QUEUE=LOCAL.parents[1]/'ops/lane-queue'
def proposal(kind,lane):
 return dict(name='packet157b-split-'+kind+'-'+lane,lane=lane,
  argv=['/usr/bin/python3','-B',str((P/'bracket_job.py').relative_to(ROOT)),'--variant','split','--kind',kind,'--lane',lane,'--output',str(P/'evidence'/('device-p157b-'+kind+'-'+lane)),'--fault-review','{REVIEW}','--authorized-device-window'],
  env_extra={},review=str((P/'fault_review.py').relative_to(ROOT)),
  plan=dict(entry_rehearsal=dict(binaries=[dict(path=str((P/'build'/m/'own-rt-iq3').relative_to(ROOT)),sha256=sha(P/'build'/m/'own-rt-iq3')) for m in ('device','gnu-host')]),host_required_available_bytes=97*1024**3+1200*1024**2,expected_seconds=[420,600],watchdog_seconds=2400))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--stage',action='store_true');a=ap.parse_args();limits()
 snapshot=LOCAL/'lineage-inputs/queue';snapshot.mkdir(exist_ok=True)
 if a.stage:
  for src in QUEUE.glob('*.py'):shutil.copy2(src,snapshot/src.name)
 rows=[]
 for lane in ('A','B'):
  for kind in ('smoke','bracket'):
   name='proposed-p157-'+('smoke' if kind=='smoke' else 'split')+'-'+lane+'.txt'
   row=proposal(kind,lane);content=json.dumps(row)+'\n';mirror=LOCAL/'proposals'/name
   if a.stage:mirror.parent.mkdir(exist_ok=True);mirror.write_text(content);continue
   assert mirror.read_text()==content,'stage proposals before sealing'
   with tempfile.TemporaryDirectory(prefix='p157-plan-') as d:
    tmp=Path(d)
    for src in snapshot.glob('*.py'):shutil.copy2(src,tmp/src.name)
    (tmp/('queue-'+lane+'.txt')).write_text(content)
    cmd=[sys.executable,'-B',str(QUEUE/'lanequeue.py'),'plan','--lane',lane,'--directory',str(tmp)]
    log=P/'evidence'/('plan-'+kind+'-'+lane+'.log')
    with log.open('w') as out:r=subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT)
    assert r.returncode==0,log.read_text()[-8000:]
   live=QUEUE/name;live.write_text(content)
   # The packet-specific report rehearsal refuses missing/empty event streams.
   cmd=[sys.executable,'-B',str(P/'rehearse_entry.py'),str(live),'--report']
   cp=subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True)
   receipt=P/'evidence'/('rehearse-'+kind+'-'+lane+'.json')
   assert cp.returncode==0,cp.stdout+cp.stderr
   rehearsal=json.loads(cp.stdout);assert rehearsal['passed'];save(receipt,rehearsal)
   rows.append(dict(proposal_name=str(live.relative_to(ROOT)),sha256=sha(live),mirror=str(mirror.relative_to(ROOT)),log=str(log.relative_to(ROOT)),log_sha256=sha(log),rehearsal=str(receipt.relative_to(ROOT)),rehearsal_sha256=sha(receipt),unit='screen-'+row['name']+'.service'))
 if a.stage:return
 for src in snapshot.glob('*.py'):assert sha(src)==sha(QUEUE/src.name),'queue changed during planning'
 save(P/'evidence/queue-plan.json',dict(passed=True,device_executed=False,live_queue_modified=False,queued=False,rows=rows,sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'p157_v5_queue_plan.py',P/'rehearse_entry.py',*snapshot.glob('*.py')]}))
if __name__=='__main__':main()
