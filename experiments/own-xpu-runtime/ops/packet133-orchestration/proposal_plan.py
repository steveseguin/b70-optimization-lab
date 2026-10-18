"""One new lane-A proposal; plan only in a temporary copy of the queue."""
import importlib.util,json,subprocess,sys,tempfile
from pathlib import Path
from source_decision import O,P,ROOT,sha,save
sys.path.insert(0,str(P))
Q=P.parents[1]/'ops/lane-queue'
PROPOSAL=Q/'proposed-p133-v5-A.txt'
def proposal():
 return dict(name='packet133-v5-A',lane='A',argv=['/usr/bin/python3','-B',str((P/'v5/bracket_job.py').relative_to(ROOT)),'--kind','bracket','--lane','A','--output',str(P/'v5/evidence/device-v5-A'),'--fault-review','{REVIEW}','--authorized-device-window'],env_extra={},review=str((P.with_name('packet130-suffix-interleave')/'v5/fault_review.py').relative_to(ROOT)))
def verify():
 row=json.loads((O/'evidence/queue-plan.json').read_text())
 assert row['passed'] and row['device_executed'] is False and row['live_queue_modified'] is False
 assert row['watchdog_seconds']>=4*max(row['expected_seconds'])
 assert json.loads(PROPOSAL.read_text())==proposal() and sha(PROPOSAL)==row['proposal_sha256']
 assert sha(O/'evidence/queue-plan.log')==row['log_sha256']
 for n,h in row['sources'].items():assert sha(ROOT/n)==h,'proposal plan source changed: '+n
 return row

def main():
 content=json.dumps(proposal())+'\n'
 if PROPOSAL.exists():assert PROPOSAL.read_text()==content
 else:PROPOSAL.write_text(content)
 with tempfile.TemporaryDirectory(prefix='packet133-plan-') as tmp:
  dest=Path(tmp)
  for f in Q.glob('*.py'):(dest/f.name).write_bytes(f.read_bytes())
  (dest/'queue-A.txt').write_bytes(PROPOSAL.read_bytes())
  cmd=[sys.executable,'-B',str(Q/'lanequeue.py'),'plan','--lane','A','--directory',str(dest)]
  log=O/'evidence/queue-plan.log'
  with log.open('w') as out:r=subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,timeout=240)
  assert r.returncode==0,log.read_text()[-5000:]
 save(O/'evidence/queue-plan.json',dict(passed=True,device_executed=False,live_queue_modified=False,proposal_sha256=sha(PROPOSAL),command=cmd,log_sha256=sha(log),expected_seconds=[720,1200],watchdog_seconds=4800,sources={str(p.relative_to(ROOT)):sha(p) for p in (Path(__file__),P/'v5/bracket_job.py',P/'v5/screen133.py',Q/'lanequeue.py')},conditional_on='exact p130 smoke, identical native selections, CPU qualification and coordinator live admission; composed smoke remains mandatory for chain'))
 verify();print('Lane A proposal planned on disposable queue; no live queue change')
if __name__=='__main__':
 from build_engine import limits
 limits();main()
