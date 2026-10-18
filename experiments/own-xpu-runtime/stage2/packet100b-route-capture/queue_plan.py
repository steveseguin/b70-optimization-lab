"""Proposed files only; real lanequeue plans always use temporary queue copies."""
import json,subprocess,sys,tempfile
from pathlib import Path
from build_engine import P,ROOT,sha,save,limits

def proposals():
 queue=P.parents[1]/'ops/lane-queue'
 review='experiments/own-xpu-runtime/stage2/screen/v4-lanes/fault_review.py'
 relative=str(P.relative_to(ROOT));result=[]
 for kind in ('capture','micro'):
  path=queue/f'proposed-p100b-{kind}-B.txt'
  job=dict(name=f'packet100b-{kind}-B',lane='B',argv=['/usr/bin/python3','-B',relative+f'/run_{kind}.py','--lane','B','--run','--fault-review','{REVIEW}','--authorized-device-window'],env_extra={},review=review)
  body=json.dumps(job)+'\n'
  if path.exists():assert path.read_text()==body
  else:path.write_text(body)
  result.append((kind+'-B','B',path))
 # Update only the existing PROPOSED jobs to use the new gate provider.
 # Frozen packet100 scripts/seals/binaries and live queue-*.txt are untouched.
 for candidate in ('down-interleave','down-tile16'):
  for label,lane in (('B-grid','B'),('A-confirm','A')):
   path=queue/f'proposed-p100-{candidate}-{label}.txt';job=json.loads(path.read_text())
   old='experiments/own-xpu-runtime/stage2/packet100-down-locality/run_screens.py'
   assert job['argv'][2] in (old,relative+'/run_grid.py')
   job['argv'][2]=relative+'/run_grid.py'
   path.write_text(json.dumps(job)+'\n')
   result.append((candidate+'-'+label,lane,path))
 return queue,result

def main():
 limits();queue,rows=proposals();plans=[]
 with tempfile.TemporaryDirectory(prefix='p100b-plan-') as tmp:
  dest=Path(tmp)
  for label,lane,path in rows:
   (dest/f'queue-{lane}.txt').write_bytes(path.read_bytes())
   cmd=[sys.executable,'-B',str(queue/'lanequeue.py'),'plan','--lane',lane,'--directory',str(dest)]
   with (P/'evidence'/('queue-plan-'+label+'.log')).open('w') as log:
    subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
   plans.append(dict(label=label,lane=lane,proposal=str(path.relative_to(ROOT)),sha256=sha(path),passed=True,runnable=False))
 save(P/'evidence/queue-plans.json',dict(passed=True,device_executed=False,live_queue_modified=False,plans=plans))
 print('six temporary queue plans PASS; no live queue changes')
if __name__=='__main__':main()
