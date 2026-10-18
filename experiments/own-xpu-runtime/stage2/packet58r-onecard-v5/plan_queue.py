"""Create the one new proposal, then plan a temporary queue; never edit live ops."""
import json,os,resource,shutil,subprocess,sys,tempfile
from pathlib import Path
from build_engine import limits,save,sha
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
QUEUE=P.parents[1]/'ops/lane-queue'

def main():
    limits()
    output=P/'evidence/card0-v5-a/route-rec'
    assert not output.parent.exists()
    proposal=QUEUE/'proposed-p58r-v5-A.txt'
    record=dict(name='packet58r-v5-A',lane='A',argv=['/usr/bin/python3','-B',str((P/'queue_runner.py').relative_to(ROOT)),
        '--arm','route-rec','--output',str(output),'--fault-review','{REVIEW}','--authorized-device-window'],
        env_extra={},review=str((P/'fault_review.py').relative_to(ROOT)))
    raw=('# CPU-prepared only: card 0; one whole-host gap, lane B paused and drained throughout.\n'
         '# Two K1 fixtures, then one load: tile16 / route+rec / tile16 / route+rec / tile16.\n'
         '# 12 prompts x 128 per view; packet49 exact tokens; full BF16 KV.\n'
         '# Expected 20-30 min including internal gaps; native/window watchdog 7200s (>=4x 30 min).\n'
         '# Host bound 109718973456 bytes + 8 GiB reserve = 118308908048 MemAvailable.\n'
         '# Diagnostic screen only; no fresh-load repeat or 512-token final gate; no automatic chain.\n'+json.dumps(record)+'\n')
    if proposal.exists():assert proposal.read_text()==raw,'proposal changed; do not overwrite'
    else:proposal.write_text(raw)
    with tempfile.TemporaryDirectory(prefix='packet58r-plan-') as directory:
        (Path(directory)/'queue-A.txt').write_text(raw)
        command=[sys.executable,'-B',str(QUEUE/'lanequeue.py'),'plan','--lane','A','--directory',directory]
        result=subprocess.run(command,cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
    log=P/'evidence/queue-plan.log';log.write_text(result.stdout+result.stderr)
    assert result.returncode==0,log.read_text()
    records=[json.loads(line) for line in result.stdout.splitlines()]
    assert len(records)==1 and records[0]['plan']=='passed'
    import queue_runner as Q
    writes=sum(Q.W.WRITES['K1' if w.startswith('K1') else w] for w in Q.ORDER)
    free=shutil.disk_usage('/').free
    assert free-writes>=25_000_000_000
    size=sum(f.stat().st_size for f in (P/'build').rglob('*') if f.is_file())
    save(P/'evidence/queue-plans.json',dict(passed=True,device_executed=False,services_started=False,live_queue_changed=False,
        temporary_queue=True,proposal_sha256=sha(proposal),records=records,output_created=output.parent.exists(),
        expected_duration_seconds=[1200,1800],watchdog_seconds=7200,scope='whole-host',card=0,
        build_receipt_sha256=sha(P/'build-receipt.json'),log_sha256=sha(log),
        storage=dict(root_free_bytes=free,planned_write_bytes=writes,stop_floor_bytes=25_000_000_000,build_bytes=size)))
    print('One temporary lane-A whole-host plan PASS; no live queue or device output created')

if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
    main()
