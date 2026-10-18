"""Plan the two proposals in an isolated temporary queue, never the live queue."""
import json,subprocess,tempfile,sys
from pathlib import Path
from build_engine import P,ROOT,sha,save,limits

def main():
 limits();queue=P.parents[1]/'ops/lane-queue';rows=[]
 for lane in ('A','B'):
  proposal=queue/f'proposed-p79-{lane}.txt'
  with tempfile.TemporaryDirectory(prefix='p79-queue-',dir=P/'build') as tmp:
   dest=Path(tmp);(dest/f'queue-{lane}.txt').write_bytes(proposal.read_bytes())
   cmd=[sys.executable,'-B',str(queue/'lanequeue.py'),'plan','--lane',lane,'--directory',str(dest)]
   cp=subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=300)
   (P/f'evidence/queue-plan-{lane}.log').write_text(cp.stdout+cp.stderr)
   assert cp.returncode==0,cp.stderr
   result=json.loads(cp.stdout);assert result['plan']=='passed'
  rows.append(dict(lane=lane,proposal_sha256=sha(proposal),command=cmd,result=result))
 save(P/'evidence/queue-plans.json',dict(passed=True,device_executed=False,live_queue_modified=False,rows=rows))
 print('temporary A/B queue plans PASS')
if __name__=='__main__':main()
