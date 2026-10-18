"""New proposals only. The real queue planner runs on disposable copies."""
import json,subprocess,sys,tempfile
from pathlib import Path
from build_engine import P,ROOT,sha,save,limits
QUEUE=P.parents[2]/'ops/lane-queue'
def proposal(kind,lane):
 return dict(name='packet137-'+kind+'-'+lane,lane=lane,argv=['/usr/bin/python3','-B',str((P/'bracket_job.py').relative_to(ROOT)),'--kind',kind,'--lane',lane,'--output',str(P/'evidence'/('device-'+('smoke' if kind=='smoke' else 'v5')+'-'+lane)),'--fault-review','{REVIEW}','--authorized-device-window'],env_extra={},review=str((P/'fault_review.py').relative_to(ROOT)))
def main():
 limits();paths=[];logs=[]
 for kind,lane in (('smoke','B'),('bracket','B'),('bracket','A')):
  path=QUEUE/('proposed-p137-'+('smoke' if kind=='smoke' else 'v5')+'-'+lane+'.txt');content=json.dumps(proposal(kind,lane))+'\n'
  if path.exists():assert path.read_text()==content,'existing proposal differs'
  else:path.write_text(content)
  paths.append(path)
 for lane in ('B','A'):
  with tempfile.TemporaryDirectory(prefix='p137-plan-') as d:
   dest=Path(d)
   for src in QUEUE.glob('*.py'):(dest/src.name).write_bytes(src.read_bytes())
   (dest/('queue-'+lane+'.txt')).write_text(''.join(p.read_text() for p in paths if p.name.endswith('-'+lane+'.txt')))
   cmd=[sys.executable,'-B',str(QUEUE/'lanequeue.py'),'plan','--lane',lane,'--directory',str(dest)]
   log=P/'evidence'/('queue-plan-'+lane+'.log')
   with log.open('w') as f:r=subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=600)
   assert r.returncode==0,log.read_text();logs.append(dict(command=cmd,path=str(log.relative_to(ROOT)),sha256=sha(log)))
 sources={str(f.relative_to(ROOT)):sha(f) for f in [*paths,P/'queue_plan.py',*(ROOT/r['path'] for r in logs)]}
 save(P/'evidence/queue-plan.json',dict(sources=sources,passed=True,device_executed=False,live_queue_modified=False,proposals={str(p.relative_to(ROOT)):sha(p) for p in paths},logs=logs,expected_seconds={'smoke':[240,360],'bracket':[720,1200]},watchdog_seconds=4800,unqueued_lanes=['A','B'],conditional_on='full exact 12x64 both smoke, CPU seal, coordinator live admission'))
 print('Three unqueued proposals; both temporary queue plans PASS')
if __name__=='__main__':main()
