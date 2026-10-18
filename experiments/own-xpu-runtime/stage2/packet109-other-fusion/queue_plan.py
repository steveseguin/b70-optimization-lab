"""Write one new proposed file and plan it only in a temporary queue copy."""
import json,subprocess,sys,tempfile
from build_engine import P,ROOT,B,sha,save,limits
from pathlib import Path
QUEUE=P.parents[1]/'ops/lane-queue'
def main():
 limits();output=P/'evidence/p109-v5-B'
 row=dict(name='packet109-v5-B',lane='B',argv=['/usr/bin/python3','-B',str((P/'bracket_job.py').relative_to(ROOT)),'--lane','B','--output',str(output),'--fault-review','{REVIEW}','--authorized-device-window'],env_extra={},review=str((P/'fault_review.py').relative_to(ROOT)))
 path=QUEUE/'proposed-p109-v5-B.txt';content=json.dumps(row)+'\n'
 if path.exists():assert path.read_text()==content
 else:path.write_text(content)
 with tempfile.TemporaryDirectory(prefix='p109-queue-',dir=B) as tmp:
  dest=Path(tmp)
  for source in QUEUE.glob('*.py'):(dest/source.name).write_bytes(source.read_bytes())
  (dest/'queue-B.txt').write_bytes(path.read_bytes())
  cmd=[sys.executable,'-B',str(QUEUE/'lanequeue.py'),'plan','--lane','B','--directory',str(dest)]
  log=P/'evidence/queue-plan-B.log'
  with log.open('w') as f:subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=240)
 save(P/'evidence/queue-plans.json',dict(passed=True,device_executed=False,live_queue_modified=False,proposal=str(path.relative_to(ROOT)),sha256=sha(path),command=cmd,log_sha256=sha(log),expected_seconds=900,watchdog_seconds=3600))
 print('lane B proposal planned; live queues unchanged; expected <=15 min, watchdog 60 min')
if __name__=='__main__':main()
