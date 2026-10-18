"""Ship the compiled micro proposal; plan it on a private queue copy only."""
import json,subprocess,sys,tempfile
from pathlib import Path
from build_engine import P,ROOT,B,limits,save,sha
def main():
    limits()
    from run_micro import build_gate
    identity=build_gate()
    queue=P.parents[1]/'ops/lane-queue'
    proposal=queue/'proposed-p108-micro-B.txt'
    job=dict(name='packet108-micro-B',lane='B',argv=['/usr/bin/python3','-B',str((P/'run_micro.py').relative_to(ROOT)),'--lane','B','--run','--fault-review','{REVIEW}','--authorized-device-window'],env_extra={},review=str((P.parent/'screen/v4-lanes/fault_review.py').relative_to(ROOT)))
    payload=json.dumps(job)+'\n'
    if proposal.exists():assert proposal.read_text()==payload,'refuse changing existing proposal'
    else:proposal.write_text(payload)
    with tempfile.TemporaryDirectory(prefix='p108-queue-',dir=B/'tmp') as tmp:
        dest=Path(tmp)
        for source in queue.glob('*.py'):(dest/source.name).write_bytes(source.read_bytes())
        (dest/'queue-B.txt').write_text(payload)
        cmd=[sys.executable,'-B',str(queue/'lanequeue.py'),'plan','--lane','B','--directory',str(dest)]
        with (P/'evidence/queue-plan-B.log').open('w') as log:
            subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=240)
    save(P/'evidence/queue-plan.json',dict(passed=True,device_executed=False,live_queue_modified=False,proposal=str(proposal.relative_to(ROOT)),proposal_sha256=sha(proposal),command=cmd,identity=identity,log_sha256=sha(P/'evidence/queue-plan-B.log')))
    print('Compiled micro proposal shipped; temporary B queue plan passes.')
if __name__=='__main__':main()
