"""Eight lane-specific proposals; temporary queues only."""
import argparse,json,subprocess,sys,tempfile,shutil
from pathlib import Path
from p145_v5_build_engine import P,LOCAL,ROOT,sha,save,limits
from bracket_config import VALUES
QUEUE=LOCAL.parents[1]/'ops/lane-queue'
def proposal(variant,kind,lane):
 return dict(name='packet145-'+variant+'-'+kind+'-'+lane,lane=lane,argv=['/usr/bin/python3','-B',str((P/'bracket_job.py').relative_to(ROOT)),'--variant',variant,'--kind',kind,'--lane',lane,'--output',str(P/'evidence'/('device-'+variant+'-'+('smoke' if kind=='smoke' else 'v5')+'-'+lane)),'--fault-review','{REVIEW}','--authorized-device-window'],env_extra={},review=str((P/'fault_review.py').relative_to(ROOT)),plan=dict(entry_rehearsal=dict(binaries=[dict(path=str((P/'build'/m/'own-rt-iq3').relative_to(ROOT)),sha256=sha(P/'build'/m/'own-rt-iq3')) for m in ('device','gnu-host')]),host_required_available_bytes=97*1024**3+1200*1024**2,expected_seconds=[240,360] if kind=='smoke' else [720,1200],watchdog_seconds=4800))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--stage',action='store_true');ap.add_argument('--router-A-only',action='store_true');a=ap.parse_args()
 limits();copies=LOCAL/'proposals';copies.mkdir(exist_ok=True);snapshot=LOCAL/'lineage-inputs/queue';snapshot.mkdir(exist_ok=True)
 for src in QUEUE.glob('*.py'):shutil.copy2(src,snapshot/src.name)
 rows=[]
 for variant in VALUES:
  for kind in ('smoke','bracket'):
   for lane in ('A','B'):
    if a.router_A_only and (variant,kind,lane)!=('router-order600','smoke','A'):continue
    name='proposed-p145-'+variant+'-'+('smoke' if kind=='smoke' else 'v5')+'-'+lane+'.txt';row=proposal(variant,kind,lane);content=json.dumps(row)+'\n';mirror=copies/name
    if a.stage:mirror.write_text(content);continue
    assert mirror.read_text()==content,'stage proposals before sealing'
    live=QUEUE/name
    with tempfile.TemporaryDirectory(prefix='p145-plan-') as d:
     tmp=Path(d)
     for src in snapshot.glob('*.py'):shutil.copy2(src,tmp/src.name)
     (tmp/('queue-'+lane+'.txt')).write_text(content)
     cmd=[sys.executable,'-B',str(QUEUE/'lanequeue.py'),'plan','--lane',lane,'--directory',str(tmp)]
     log=P/'evidence'/('plan-'+variant+'-'+kind+'-'+lane+'.log')
     with log.open('w') as stream:r=subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,timeout=300)
     assert r.returncode==0,log.read_text()[-6000:]
    live.write_text(content)
    rehearse=[sys.executable,'-B',str(QUEUE.parent/'rehearse_entry.py'),str(live),'--json']
    r=subprocess.run(rehearse,cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180);assert r.returncode==0,r.stdout+r.stderr
    rehearsal=json.loads(r.stdout);assert rehearsal['passed']
    receipt=P/'evidence'/('rehearse-'+variant+'-'+kind+'-'+lane+'.json');save(receipt,rehearsal)
    rows.append(dict(proposal_name=str(live.relative_to(ROOT)),sha256=sha(live),mirror=str(mirror.relative_to(ROOT)),log=str(log.relative_to(ROOT)),log_sha256=sha(log),rehearsal=str(receipt.relative_to(ROOT)),rehearsal_sha256=sha(receipt),unit='screen-'+row['name']+'.service',**row['plan']))
 if a.stage:return
 for src in snapshot.glob('*.py'):assert sha(src)==sha(QUEUE/src.name),'queue implementation changed during planning'
 paths=[P/'p145_v5_queue_plan.py',*snapshot.glob('*.py'),*(ROOT/r['log'] for r in rows)]
 save(P/'evidence/queue-plan.json',dict(passed=True,device_executed=False,live_queue_modified=False,queued=False,rows=rows,sources={str(f.relative_to(ROOT)):sha(f) for f in paths}))
if __name__=='__main__':main()
