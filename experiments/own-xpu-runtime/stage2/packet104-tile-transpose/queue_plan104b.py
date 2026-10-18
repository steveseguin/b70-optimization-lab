"""New proposals and disposable queue plans only; never enqueue."""
import json,subprocess,sys,tempfile
from pathlib import Path
from build_engine import P,ROOT,sha,save,limits

def main():
 limits();queue=P.parents[1]/'ops/lane-queue';records=[]
 with tempfile.TemporaryDirectory(prefix='p104b-queue-plan-') as tmp:
  for label,lane in (('B-grid','B'),('A-confirm','A')):
   path=queue/('proposed-p104b-'+label+'.txt')
   row=dict(name='packet104b-'+label,lane=lane,argv=['/usr/bin/python3','-B',str(P.relative_to(ROOT))+'/run_screens.py','--direction','B-grid','--lane',lane,'--run','--fault-review','{REVIEW}','--authorized-device-window'],env_extra={},review='experiments/own-xpu-runtime/stage2/screen/v4-lanes/fault_review.py')
   body=json.dumps(row)+'\n'
   if path.exists():assert path.read_text()==body
   else:path.write_text(body)
   (Path(tmp)/('queue-'+lane+'.txt')).write_text(body)
   cmd=[sys.executable,'-B',str(queue/'lanequeue.py'),'plan','--lane',lane,'--directory',tmp]
   with (P/'evidence'/('queue-plan104b-'+label+'.log')).open('w') as log:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
   records.append(dict(proposal=str(path.relative_to(ROOT)),sha256=sha(path),command=cmd,passed=True))
 save(P/'evidence/queue-plans104b.json',dict(passed=True,device_executed=False,live_queue_modified=False,plans=records,baseline='packet97 selected + down-tile16 + E1; plain gate candidate removes E1',confirmation='A execution refuses until all four B screens complete, exact, unchanged acceptance, winner beats both controls'))
 print('both temporary queue plans PASS')
if __name__=='__main__':main()
