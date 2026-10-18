"""Write new proposals; run the real coordinator planner on temporary queues."""
import json,subprocess,sys,tempfile
from pathlib import Path
from build_engine import P,limits
from build_images import sha
ROOT=P.parents[3];QUEUE=P.parents[1]/'ops/lane-queue'
def main():
 limits()
 import micro_gate
 micro_gate.prerequisites(P)
 rows=[]
 for repeat in (1,2):
  rows.append(dict(name=f'packet115-micro-B-{repeat}',lane='B',argv=['/usr/bin/python3','-B',str((P/'run_micro.py').relative_to(ROOT)),'--run','--repeat',str(repeat),'--lane','B','--fault-review','{REVIEW}','--authorized-device-window'],env_extra={},review=str((P.parent/'screen/v4-lanes/fault_review.py').relative_to(ROOT))))
 proposal=QUEUE/'proposed-p115-micro-B.txt';proposal.write_text(''.join(json.dumps(r)+'\n' for r in rows))
 with tempfile.TemporaryDirectory(prefix='p115-plan-',dir=P/'build/tmp') as td:
  dest=Path(td)
  for src in QUEUE.glob('*.py'):(dest/src.name).write_bytes(src.read_bytes())
  (dest/'queue-B.txt').write_bytes(proposal.read_bytes())
  cmd=[sys.executable,'-B',str(QUEUE/'lanequeue.py'),'plan','--lane','B','--directory',str(dest)]
  log=P/'evidence/micro-queue-plan.log'
  with log.open('w') as f:r=subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=240)
  receipt=dict(passed=r.returncode==0,device_executed=False,live_queue_modified=False,proposal=str(proposal.relative_to(ROOT)),proposal_sha256=sha(proposal),jobs=len(rows),command=cmd,returncode=r.returncode,log_sha256=sha(log),expected_seconds_each=180,watchdog_seconds_each=900)
  (P/'evidence/micro-queue-plan.json').write_text(json.dumps(receipt,indent=2)+'\n')
  print(log.read_text()[-4000:]);assert r.returncode==0
 print('two fresh micro jobs planned on a temporary queue; live queues untouched')
if __name__=='__main__':main()
