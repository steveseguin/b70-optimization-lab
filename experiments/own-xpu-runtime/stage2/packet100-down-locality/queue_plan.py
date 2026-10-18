"""Write new proposals only; execute their plans on disposable queue copies."""
import json,subprocess,sys,tempfile
from pathlib import Path
from build_engine import P,ROOT,sha,save,limits

def proposals():
 queue=P.parents[1]/'ops/lane-queue';relative=str(P.relative_to(ROOT));review='experiments/own-xpu-runtime/stage2/screen/v4-lanes/fault_review.py'
 rows=[('micro-B','B',['/usr/bin/python3','-B',relative+'/run_micro.py','--lane','B','--run','--fault-review','{REVIEW}','--authorized-device-window'])]
 for name in ('down-interleave','down-tile16'):
  for label,lane in (('B-grid','B'),('A-confirm','A')):
   rows.append((name+'-'+label,lane,['/usr/bin/python3','-B',relative+'/run_screens.py','--candidate',name,'--direction','B-grid','--lane',lane,'--run','--fault-review','{REVIEW}','--authorized-device-window']))
 paths=[]
 for label,lane,argv in rows:
  p=queue/('proposed-p100-'+label+'.txt');body=json.dumps(dict(name='packet100-'+label,lane=lane,argv=argv,env_extra={},review=review))+'\n'
  if p.exists():assert p.read_text()==body,'never overwrite different proposed job'
  else:p.write_text(body)
  paths.append((label,lane,p))
 return queue,paths

def main():
 limits();queue,paths=proposals();records=[]
 with tempfile.TemporaryDirectory(prefix='p100-queue-plan-') as tmp:
  dest=Path(tmp)
  for label,lane,path in paths:
   (dest/('queue-'+lane+'.txt')).write_bytes(path.read_bytes())
   cmd=[sys.executable,'-B',str(queue/'lanequeue.py'),'plan','--lane',lane,'--directory',str(dest)]
   with (P/'evidence'/('queue-plan-'+label+'.log')).open('w') as log:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
   records.append(dict(label=label,lane=lane,proposal=str(path.relative_to(ROOT)),sha256=sha(path),command=cmd,passed=True,runnable=False))
 save(P/'evidence/queue-plans.json',dict(passed=True,device_executed=False,live_queue_modified=False,plans=records,execution_gate='receipt-bound route bytes, measured >=15% kernel gain, exact B winner before A confirmation; records on A'))
 print('five temporary queue plans PASS; no live queue write')
if __name__=='__main__':main()
