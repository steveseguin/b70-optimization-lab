"""Write only the new proposed job; invoke the real planner on a temp queue."""
import json,subprocess,sys,tempfile
from pathlib import Path
from build_engine import P,ROOT,sha,save,limits
def main():
 limits();queue=P.parents[1]/'ops/lane-queue'
 path=queue/'proposed-p129-accept-B.txt'
 row=dict(name='p129-acceptance-B-a',lane='B',argv=['/usr/bin/python3','-B',str((P/'run_screen.py').relative_to(ROOT)),'--lane','B','--output',str(P/'evidence/device-B'),'--fault-review','{REVIEW}','--authorized-device-window'],env_extra={},review=str((P.parent/'screen/v4-lanes/fault_review.py').relative_to(ROOT)))
 path.write_text(json.dumps(row,separators=(',',':'))+'\n')
 with tempfile.TemporaryDirectory(prefix='p129-queue-',dir=P/'build/tmp') as tmp:
  dest=Path(tmp)
  for source in queue.glob('*.py'):(dest/source.name).write_bytes(source.read_bytes())
  (dest/'queue-B.txt').write_bytes(path.read_bytes())
  command=[sys.executable,'-B',str(queue/'lanequeue.py'),'plan','--lane','B','--directory',str(dest)]
  log=P/'evidence/queue-plan-B.log'
  with log.open('w') as f:subprocess.run(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=240)
 save(P/'evidence/queue-plan.json',dict(passed=True,device_executed=False,live_queue_modified=False,proposal=str(path.relative_to(ROOT)),proposal_sha256=sha(path),command=command,log_sha256=sha(log)))
 print('One acceptance-only lane-B job planned on temporary queue; live queue untouched')
if __name__=='__main__':main()
