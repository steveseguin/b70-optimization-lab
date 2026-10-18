"""Validate proposals in a private plan directory; never touch live queues."""
import json,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
Q=P.parents[1]/'ops/lane-queue'
def main():
 dest=P/'queue-plan';dest.mkdir(exist_ok=True)
 results={}
 for lane in ('A','B'):
  proposal=Q/f'proposed-p73-{lane}.txt'
  (dest/f'queue-{lane}.txt').write_bytes(proposal.read_bytes())
  cmd=[sys.executable,'-B',str(Q/'lanequeue.py'),'plan','--lane',lane,'--directory',str(dest)]
  with (P/'evidence'/f'lanequeue-plan-{lane}.log').open('w') as log:
   subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
  results[lane]=dict(proposal=str(proposal.relative_to(ROOT)),command=cmd,passed=True)
 (P/'evidence/queue-plans.json').write_text(json.dumps(dict(passed=True,device_executed=False,live_queues_modified=False,lanes=results),indent=2)+'\n')
 print('both proposed queues pass lanequeue.py plan; no jobs launched')
if __name__=='__main__':main()
