"""Plan every proposed packet95 job in a disposable queue copy."""
import json,subprocess,sys,tempfile
from pathlib import Path
from build_engine import P,ROOT,save,limits

def main():
 limits();queue=P.parents[1]/'ops/lane-queue';rows=[]
 with tempfile.TemporaryDirectory(prefix='p95-queue-plan-') as tmp:
  dest=Path(tmp)
  sources=sorted(queue.glob('proposed-p95-*.txt'));assert len(sources)==8
  for source in sources:
   entry=json.loads(source.read_text());lane=entry['lane'];(dest/f'queue-{lane}.txt').write_bytes(source.read_bytes())
   command=[sys.executable,'-B',str(queue/'lanequeue.py'),'plan','--lane',lane,'--directory',str(dest)]
   with (P/'evidence'/('queue-plan-'+source.stem+'.log')).open('w') as log:
    subprocess.run(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
   rows.append(dict(lane=lane,proposal=str(source.relative_to(ROOT)),command=command,passed=True))
 save(P/'evidence/queue-plans.json',dict(passed=True,device_executed=False,live_queue_modified=False,plans=rows))
 print('eight temporary queue plans PASS')
if __name__=='__main__':main()
