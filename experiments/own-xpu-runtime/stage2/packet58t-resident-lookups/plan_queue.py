"""CPU plan on a private temporary queue; no live queue writes or launches."""
import json,os,resource,subprocess,sys,tempfile
from pathlib import Path
from build_engine import limits,sha,save
P=Path(__file__).resolve().parent;ROOT=P.parents[3];QUEUE=P.parents[1]/'ops/lane-queue'
def main():
    limits();proposal=QUEUE/'proposed-p58t-screen-A.txt';raw=proposal.read_bytes()
    with tempfile.TemporaryDirectory(prefix='p58t-plan-') as directory:
        temp=Path(directory);(temp/'queue-A.txt').write_bytes(raw)
        cmd=[sys.executable,'-B',str(QUEUE/'lanequeue.py'),'plan','--lane','A','--directory',str(temp)]
        r=subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
    log=P/'evidence/queue-plan.log';log.write_text(r.stdout+r.stderr);assert r.returncode==0,log.read_text()
    rows=[json.loads(line) for line in r.stdout.splitlines()];assert len(rows)==1 and rows[0]['plan']=='passed'
    assert not (P/'evidence/card0-resident-a').exists()
    save(P/'evidence/queue-plans.json',dict(passed=True,device_executed=False,temporary_queue=True,live_queue_changed=False,services_started=False,
        rows=rows,proposal_sha256=sha(proposal),log_sha256=sha(log),expected_seconds=[900,1500],watchdog_seconds=7200))
    print('one temporary whole-host resident bracket plan PASS')
if __name__=='__main__':
    # This process only plans; no cap can reach a device launch.
    resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));main()
