#!/usr/bin/env python3
"""Plan the proposed jobs on a temporary queue. Never writes a live queue."""
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import tempfile

P=Path(__file__).resolve().parent
ROOT=P.parents[3]
QUEUE=P.parents[1]/'ops/lane-queue'


def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    resource.setrlimit(resource.RLIMIT_AS,(8_000_000_000,8_000_000_000))
    proposal=QUEUE/'proposed-p58n-screen-A.txt'
    raw=proposal.read_bytes()
    with tempfile.TemporaryDirectory(prefix='packet58n-plan-') as temp:
        directory=Path(temp)
        (directory/'queue-A.txt').write_bytes(raw)
        command=['/usr/bin/python3','-B',str(QUEUE/'lanequeue.py'),'plan','--lane','A','--directory',str(directory)]
        result=subprocess.run(command,cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True)
    log=P/'evidence/queue-plan.log';log.write_text(result.stdout+result.stderr)
    assert result.returncode==0, log.read_text()
    records=[json.loads(line) for line in result.stdout.splitlines()]
    assert len(records)==3 and all(r['plan']=='passed' for r in records)
    assert not (P/'evidence/card0-loo-a').exists()
    receipt=dict(passed=True,device_executed=False,services_started=False,live_queue_changed=False,
        temporary_queue=True,proposal_sha256=hashlib.sha256(raw).hexdigest(),records=records,
        output_created=False,expected_duration_seconds=[1980,2340],log_sha256=hashlib.sha256(log.read_bytes()).hexdigest())
    (P/'evidence/queue-plans.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))


if __name__=='__main__':main()
