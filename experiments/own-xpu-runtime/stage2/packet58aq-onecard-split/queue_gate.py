"""Real lanequeue plan against temporary queues; never touch live queue files."""
import json,subprocess,tempfile,sys
from pathlib import Path
from build_engine import P,sha,save
OPS=P.parents[1]/'ops';ROOT=P.parents[3]
def main():
 records=[]
 for tag in ('split','smoke'):
  proposal=OPS/'lane-queue'/f'proposed-p58aq-{tag}-A.txt'
  with tempfile.TemporaryDirectory(prefix='p58aq-queue-') as directory:
   d=Path(directory);(d/'queue-A.txt').write_bytes(proposal.read_bytes())
   cmd=[sys.executable,'-B',str(OPS/'lane-queue/lanequeue.py'),'plan','--lane','A','--directory',str(d)]
   cp=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True)
   (P/'evidence'/f'queue-plan-{tag}.log').write_text(cp.stdout+cp.stderr)
   assert cp.returncode==0,cp.stdout[-5000:]+cp.stderr[-2000:]
  sys.path.insert(0,str(OPS/'lane-queue'));import pin_guard
  job=json.loads(next(x for x in proposal.read_text().splitlines() if x.startswith('{')))
  pin=pin_guard.check_job(job)
  records.append(dict(tag=tag,proposal_sha256=sha(proposal),passed=True,pins=pin))
 save(P/'evidence/queue-plans.json',dict(passed=True,device_executed=False,records=records,live_queue_changed=False))
 print('PASS real lanequeue plans and private pin closure')
if __name__=='__main__':main()
