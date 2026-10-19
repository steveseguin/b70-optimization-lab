"""Lane-B proposals and temporary plans only. Never edit live queue files."""
import argparse,json,subprocess,sys,tempfile,shutil
from p154_v5_build_engine import P,LOCAL,ROOT,sha,save,limits
QUEUE=LOCAL.parents[1]/'ops/lane-queue'
def proposal(kind):
 return dict(name='packet154-split-'+kind+'-B',lane='B',argv=['/usr/bin/python3','-B',str((P/'bracket_job.py').relative_to(ROOT)),'--variant','split','--kind',kind,'--lane','B','--output',str(P/'evidence'/('device-split-'+('smoke' if kind=='smoke' else 'v5')+'-B')),'--fault-review','{REVIEW}','--authorized-device-window'],env_extra={},review=str((P/'fault_review.py').relative_to(ROOT)),plan=dict(entry_rehearsal=dict(binaries=[dict(path=str((P/'build'/m/'own-rt-iq3').relative_to(ROOT)),sha256=sha(P/'build'/m/'own-rt-iq3')) for m in ('device','gnu-host')]),host_required_available_bytes=97*1024**3+1200*1024**2,expected_seconds=[420,600],watchdog_seconds=2400))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--stage',action='store_true');a=ap.parse_args()
 limits();snapshot=LOCAL/'lineage-inputs/queue';snapshot.mkdir(exist_ok=True)
 for src in QUEUE.glob('*.py'):shutil.copy2(src,snapshot/src.name)
 rows=[]
 for kind in ('smoke','bracket'):
  name='proposed-p154-'+('smoke' if kind=='smoke' else 'split')+'-B.txt';row=proposal(kind);content=json.dumps(row)+'\n';mirror=LOCAL/'proposals'/name
  if a.stage:mirror.write_text(content);continue
  assert mirror.read_text()==content,'stage proposals before sealing'
  with tempfile.TemporaryDirectory(prefix='p154-plan-') as d:
   from pathlib import Path
   tmp=Path(d)
   for src in snapshot.glob('*.py'):shutil.copy2(src,tmp/src.name)
   (tmp/'queue-B.txt').write_text(content)
   cmd=[sys.executable,'-B',str(QUEUE/'lanequeue.py'),'plan','--lane','B','--directory',str(tmp)]
   log=P/'evidence'/('plan-'+kind+'-B.log')
   with log.open('w') as out:r=subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT)
   assert r.returncode==0,log.read_text()[-8000:]
  live=QUEUE/name;live.write_text(content)
  r=subprocess.run([sys.executable,'-B',str(QUEUE.parent/'rehearse_entry.py'),str(live),'--report','--json'],cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True)
  (P/'evidence'/('rehearse-'+kind+'.log')).write_text(r.stdout+r.stderr)
  assert r.returncode==0,r.stdout+r.stderr
  rehearsal=json.loads(r.stdout);assert rehearsal['passed']
  receipt=P/'evidence'/('rehearse-'+kind+'.json');save(receipt,rehearsal)
  rows.append(dict(proposal_name=str(live.relative_to(ROOT)),sha256=sha(live),mirror=str(mirror.relative_to(ROOT)),log=str(log.relative_to(ROOT)),log_sha256=sha(log),rehearsal=str(receipt.relative_to(ROOT)),rehearsal_sha256=sha(receipt),unit='screen-'+row['name']+'.service'))
 if a.stage:return
 for src in snapshot.glob('*.py'):assert sha(src)==sha(QUEUE/src.name),'queue changed during planning'
 save(P/'evidence/queue-plan.json',dict(passed=True,device_executed=False,live_queue_modified=False,queued=False,rows=rows,sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'p154_v5_queue_plan.py',*snapshot.glob('*.py')]}))
if __name__=='__main__':main()
