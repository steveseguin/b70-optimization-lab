"""Plan an existing proposal on a temporary queue, never on a live queue."""
import json,resource,subprocess,sys,tempfile
from pathlib import Path
from build_engine import P,ROOT,sha,save
QUEUE=P.parents[1]/'ops/lane-queue'
def main():
    proposal=QUEUE/'proposed-p58af-measure-A.txt';assert proposal.read_bytes()==(P/'proposals'/proposal.name).read_bytes()
    with tempfile.TemporaryDirectory(prefix='p58af-plan-') as tmp:
        (Path(tmp)/'queue-A.txt').write_bytes(proposal.read_bytes())
        result=subprocess.run([sys.executable,'-B',str(QUEUE/'lanequeue.py'),'plan','--lane','A','--directory',tmp],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
    log=P/'evidence/queue-plan.log';log.write_text(result.stdout+result.stderr)
    if result.returncode:raise ValueError(log.read_text()[-5000:])
    rows=[json.loads(line) for line in result.stdout.splitlines()];assert rows and all(r['plan']=='passed' for r in rows)
    save(P/'evidence/queue-plan.json',dict(passed=True,device_executed=False,temporary_queue=True,live_queue_changed=False,
        plan=rows,proposal=str(proposal.relative_to(ROOT)),proposal_sha256=sha(proposal),build_receipt_sha256=sha(P/'build-receipt.json')))
    print('temporary queue plan passed; proposal remains unqueued')
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
