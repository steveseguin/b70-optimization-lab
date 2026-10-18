"""Plan only in a temporary queue; leave the live queues untouched."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from build_engine import P, ROOT, save, sha, limits


def main():
    limits()
    queue=P.parents[1]/'ops/lane-queue'
    proposal=queue/'proposed-p77-B.txt'
    with tempfile.TemporaryDirectory(prefix='packet77-queue-plan-') as tmp:
        dest=Path(tmp)
        (dest/'queue-B.txt').write_bytes(proposal.read_bytes())
        cmd=[sys.executable,'-B',str(queue/'lanequeue.py'),'plan','--lane','B','--directory',str(dest)]
        cp=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
        (P/'evidence/queue-plan-B.log').write_text(cp.stdout+cp.stderr)
        cp.check_returncode()
        result=json.loads(cp.stdout)
        assert '"plan": "passed"' in cp.stdout, 'static-only plan is insufficient'
    save(P/'evidence/queue-plan.json',dict(passed=True,device_executed=False,
         live_queue_modified=False,proposal_sha256=sha(proposal),command=cmd,result=result))
    print('temporary lane-B queue plan PASS')


if __name__=='__main__':main()
