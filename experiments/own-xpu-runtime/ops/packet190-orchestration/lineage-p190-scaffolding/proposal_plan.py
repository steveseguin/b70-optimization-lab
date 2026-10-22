"""Plan disposable queues; every --plan reaches real CPU admission."""
import json,subprocess,sys,tempfile
from pathlib import Path
from source_decision import O,P,ROOT,sha,save
sys.path.insert(0,str(P))
Q=P.parents[1]/'ops/lane-queue';PROPOSAL=Q/'proposed-p136-confirm-A.txt'
def proposal():
 from confirm136 import output
 return [dict(name='packet136b-confirm-A-'+('smoke12' if i==-1 else str(i)),lane='A',argv=['/usr/bin/python3','-B',str((P/'confirm136.py').relative_to(ROOT)),'--index',str(i),'--output',str(output(i)),'--fault-review','{REVIEW}','--authorized-device-window'],env_extra={},review=str((P.parent/'screen/v4-lanes/fault_review.py').relative_to(ROOT))) for i in range(-1,5)]
def verify():
 row=json.loads((O/'evidence/queue-plan.json').read_text())
 assert row['passed'] and row['device_executed'] is False and row['live_queue_modified'] is False
 assert row['watchdog_seconds']>=4*max(row['expected_seconds'])
 assert [json.loads(line) for line in PROPOSAL.read_text().splitlines()]==proposal() and sha(PROPOSAL)==row['proposal_sha256']
 assert sha(O/'evidence/queue-plan.log')==row['log_sha256']
 for n,h in row['sources'].items():assert sha(ROOT/n)==h,'proposal plan source changed: '+n
 from source_gate136 import verify_sources
 verify_sources(row['sources'])
 return row
def main():
 content=''.join(json.dumps(job)+'\n' for job in proposal())
 with tempfile.TemporaryDirectory(prefix='packet136-plan-') as tmp:
  dest=Path(tmp);(dest/'queue-A.txt').write_text(content)
  cmd=[sys.executable,'-B',str(O/'lanequeue.py'),'plan','--lane','A','--directory',str(dest)]
  log=O/'evidence/queue-plan.log'
  with log.open('w') as out:r=subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,timeout=600)
  assert r.returncode==0,log.read_text()[-5000:]
 with (O/'evidence/chain-plan.log').open('w') as log:
  r=subprocess.run([sys.executable,'-B',str(O/'chain_entry.py'),'queue','--plan','--output-root',str(P/'build/device-cards01-a')],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=240)
 assert r.returncode==0,(O/'evidence/chain-plan.log').read_text()[-4000:]
 PROPOSAL.write_text(content)
 row=json.loads((O/'proposal-spec.json').read_text())
 row.update(proposal_sha256=sha(PROPOSAL),command=cmd,log_sha256=sha(O/'evidence/queue-plan.log'),sources={str(p.relative_to(ROOT)):sha(p) for p in (Path(__file__),P/'confirm136.py',P/'compare136.py',O/'lanequeue.py',O/'proposal-spec.json',O/'evidence/chain-plan.log')})
 save(O/'evidence/queue-plan.json',row);verify()
 print('Six lane-A jobs and complete chain planned; live queues untouched')
if __name__=='__main__':
 from build_engine import limits
 limits();main()
