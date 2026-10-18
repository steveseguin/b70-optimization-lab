"""Plan proposed jobs in a temporary queue; never mutate the live queue."""
import json,subprocess,sys,tempfile
from pathlib import Path
from build_engine import P,ROOT,save,limits

def main():
 limits();queue=P.parents[1]/'ops/lane-queue';rows=[]
 with tempfile.TemporaryDirectory(prefix='p83-queue-plan-') as tmp:
  dest=Path(tmp)
  for lane,mode in ((l,m) for l in ('A','B') for m in ('grid','confirm')):
   source=queue/f'proposed-p83-{lane}-{mode}.txt';(dest/f'queue-{lane}.txt').write_bytes(source.read_bytes())
   command=[sys.executable,'-B',str(queue/'lanequeue.py'),'plan','--lane',lane,'--directory',str(dest)]
   with (P/'evidence'/f'queue-plan-{lane}-{mode}.log').open('w') as log:
    subprocess.run(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
   rows.append(dict(lane=lane,mode=mode,proposal=str(source.relative_to(ROOT)),command=command,passed=True))
 save(P/'evidence/queue-plans.json',dict(passed=True,device_executed=False,live_queue_modified=False,plans=rows))
 print('temporary A/B queue plans PASS; B remains winner-gated')
if __name__=='__main__':main()
