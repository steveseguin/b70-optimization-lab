"""Create a conditional proposal; never write a live queue."""
import json,subprocess,sys,tempfile
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[4];QUEUE=P.parents[2]/'ops/lane-queue'

def proposal():
 return dict(name='packet117-v5-B',lane='B',argv=['/usr/bin/python3','-B',str((P/'bracket_job.py').relative_to(ROOT)),'--lane','B','--output',str(P/'evidence/device-v5-B'),'--fault-review','{REVIEW}','--authorized-device-window'],env_extra={},review=str((P/'fault_review.py').relative_to(ROOT)))

def main():
 from build_engine import limits,save,sha
 limits();P.joinpath('build').mkdir(exist_ok=True)
 path=QUEUE/'proposed-p117-v5-B.txt';content=json.dumps(proposal())+'\n'
 if path.exists():assert path.read_text()==content,'existing proposal differs'
 else:path.write_text(content)
 with tempfile.TemporaryDirectory(prefix='p117-plan-',dir=P/'build') as tmp:
  dest=Path(tmp)
  for src in QUEUE.glob('*.py'):(dest/src.name).write_bytes(src.read_bytes())
  (dest/'queue-B.txt').write_text(content)
  cmd=[sys.executable,'-B',str(QUEUE/'lanequeue.py'),'plan','--lane','B','--directory',str(dest)]
  log=P/'evidence/queue-plan-B.log';log.parent.mkdir(exist_ok=True)
  with log.open('w') as f:result=subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=240)
  save(P/'evidence/queue-plan.json',dict(passed=result.returncode==0,device_executed=False,live_queue_modified=False,proposal=str(path.relative_to(ROOT)),proposal_sha256=sha(path),command=cmd,returncode=result.returncode,log_sha256=sha(log),expected_seconds=900,watchdog_seconds=3600,conditional_on='two fresh exact micro processes in both orders <=0.70 production, selected-view CPU seal'))
  print('proposal saved; temporary plan return code',result.returncode)
  return result.returncode

if __name__=='__main__':raise SystemExit(main())
