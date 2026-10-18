"""New proposals only; plan smoke then conditional bracket on a temporary queue."""
import json,subprocess,sys,tempfile
from pathlib import Path
from build_engine import P,ROOT,sha,save,limits
QUEUE=P.parents[2]/'ops/lane-queue'
def proposal(kind):
 return dict(name='packet137-'+kind+'-B',lane='B',argv=['/usr/bin/python3','-B',str((P/'bracket_job.py').relative_to(ROOT)),'--kind',kind,'--lane','B','--output',str(P/'evidence'/('device-smoke-B' if kind=='smoke' else 'device-v5-B')),'--fault-review','{REVIEW}','--authorized-device-window'],env_extra={},review=str((P/'fault_review.py').relative_to(ROOT)))
def main():
 limits();paths=[]
 for kind in ('smoke','bracket'):
  path=QUEUE/('proposed-p137-'+kind+'-B.txt');content=json.dumps(proposal(kind))+'\n'
  if path.exists():assert path.read_text()==content,'existing proposal differs'
  else:path.write_text(content)
  paths.append(path)
 with tempfile.TemporaryDirectory(prefix='p137-plan-') as d:
  dest=Path(d)
  for src in QUEUE.glob('*.py'):(dest/src.name).write_bytes(src.read_bytes())
  (dest/'queue-B.txt').write_text(''.join(p.read_text() for p in paths))
  cmd=[sys.executable,'-B',str(QUEUE/'lanequeue.py'),'plan','--lane','B','--directory',str(dest)]
  log=P/'evidence/queue-plan-B.log'
  with log.open('w') as f:r=subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=240)
  assert r.returncode==0,log.read_text()
 save(P/'evidence/queue-plan.json',dict(passed=True,device_executed=False,live_queue_modified=False,proposals={str(p.relative_to(ROOT)):sha(p) for p in paths},command=cmd,log_sha256=sha(log),expected_seconds={'smoke':[240,360],'bracket':[720,1200]},watchdog_seconds=4800,conditional_on='full exact 12x64 smoke, source-bound CPU gates, coordinator live admission'))
 print('Two proposed files, complete temporary queue plan PASS')
if __name__=='__main__':
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
