"""Create proposed files only; invoke real queue plan against a temporary copy."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from build_engine import P, ROOT, save, sha, limits
from policy import VIEWS

def main():
    limits();queue=P.parents[1]/'ops/lane-queue';results=[]
    for lane in ('B','A'):
        proposal=queue/f'proposed-p86-{lane}.txt'
        lines=[]
        for view in VIEWS:
            output=P.parent/'screen/v4-lanes/evidence'/f'packet86-{lane}-a'/view
            lines.append(dict(name=f'packet86-{view}-{lane}',lane=lane,
                 argv=['/usr/bin/python3','-B',str((P/'run_screen.py').relative_to(ROOT)),
                 '--view',view,'--lane',lane,'--output',str(output.relative_to(ROOT)),
                 '--fault-review','{REVIEW}','--authorized-device-window'],env_extra={},
                 review='experiments/own-xpu-runtime/stage2/screen/v4-lanes/fault_review.py'))
        content=''.join(json.dumps(row,separators=(',',':'))+'\n' for row in lines)
        if proposal.exists():assert proposal.read_text()==content,'do not overwrite proposal'
        else:proposal.write_text(content)
        with tempfile.TemporaryDirectory(prefix='packet86-queue-plan-') as tmp:
            d=Path(tmp);(d/f'queue-{lane}.txt').write_bytes(proposal.read_bytes())
            cmd=[sys.executable,'-B',str(queue/'lanequeue.py'),'plan','--lane',lane,'--directory',str(d)]
            cp=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=300)
            (P/'evidence'/f'queue-plan-{lane}.log').write_text(cp.stdout+cp.stderr);cp.check_returncode()
            result=[json.loads(line) for line in cp.stdout.splitlines() if line.strip()];assert cp.stdout.count('"plan": "passed"')==len(VIEWS),cp.stdout
            results.append(dict(lane=lane,proposal_sha256=sha(proposal),command=cmd,result=result))
        print(lane,'temporary queue: all views planned PASS',flush=True)
    save(P/'evidence/queue-plans.json',dict(passed=True,device_executed=False,live_queue_modified=False,results=results))
if __name__=='__main__':main()
