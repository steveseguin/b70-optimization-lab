"""Emit two proposals, validate each on a temporary queue; never queue live jobs."""
import json,resource,shutil,subprocess,sys,tempfile
from pathlib import Path
from build_engine import P,ROOT,limits,save,sha
from views import DEFAULT_MAINTENANCE
QUEUE=P.parents[1]/'ops/lane-queue'

def main():
    emit_only="--emit-only" in sys.argv
    limits();assert not (P/'evidence/card0-capacity-a').exists()
    library=json.loads((P/'library-path.json').read_text())['LD_LIBRARY_PATH']
    records=[]
    for arm,tag,expected in [('smoke','smoke',[600,900]),('max','v5',[1200,1800])]:
        output=P/'evidence/card0-capacity-a'/arm
        record=dict(name='packet58x-'+tag+'-A',lane='A',argv=['/usr/bin/python3','-B',str((P/'queue_runner.py').relative_to(ROOT)),
                    '--cache-maintenance',DEFAULT_MAINTENANCE,'--arm',arm,'--output',str(output),'--fault-review','{REVIEW}',
                    '--library-path',library,'--authorized-device-window'],
                    env_extra={},review=str((P/'fault_review.py').relative_to(ROOT)))
        raw=('# CPU proposal only; card 0, lane A, whole host; lane B paused/drained throughout.\n'
             '# Packet58x: larger cache; real queue/window startup gate and lanequeue-derived unit identity.\n'
             '# Two K1 fixtures precede one model load. Smoke: 12 x 64 max; v5: 12 x 128 18GB/max/18GB/max/18GB; fixed overlap maintenance.\n'
             '# Packet58xb follows p58wb: A0 exact/reported warm-up only; both max views >= 1.005x each A1/A2 control; warm drift <= 3%.\n'
             '# Native and Python check every token against iq3-p49-split32-v1. The v5 runner refuses without this exact smoke.\n'
             f'# Expected {expected[0]}-{expected[1]} seconds; watchdog 7200 seconds >= 4x upper estimate.\n'
             '# Required host MemAvailable 98989727744 bytes, including unchanged 8 GiB reserve; BF16 KV, one 21.5527296 GB allocation, usage capped per view.\n'
             '# No device run, live queue change, record chain or submission performed by preparation.\n'+json.dumps(record)+'\n')
        proposal=QUEUE/('proposed-p58x-'+tag+'-A.txt')
        if proposal.exists():
            existing = [json.loads(line) for line in proposal.read_text().splitlines()
                        if line.strip() and not line.lstrip().startswith('#')]
            # Owner-authorized prelaunch 58xb amendment: only serial -> overlap.
            legacy=dict(record,argv=list(record['argv']))
            legacy['argv'][legacy['argv'].index('--cache-maintenance')+1]='serial'
            assert existing in ([record],[legacy]), 'never overwrite unrelated changed proposal job'
        if emit_only:
            proposal.write_text(raw)
            continue
        with tempfile.TemporaryDirectory(prefix='p58x-plan-') as directory:
            (Path(directory)/'queue-A.txt').write_text(raw)
            cmd=[sys.executable,'-B',str(QUEUE/'lanequeue.py'),'plan','--lane','A','--directory',directory]
            r=subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
        log=P/'evidence'/('queue-plan-'+tag+'.log');log.write_text(r.stdout+r.stderr)
        assert r.returncode==0,log.read_text()
        plan=[json.loads(x) for x in r.stdout.splitlines()];assert len(plan)==1 and plan[0]['plan']=='passed'
        proposal.write_text(raw)  # Only the named proposal, after its temporary plan passed.
        records.append(dict(arm=arm,proposal=str(proposal.relative_to(ROOT)),proposal_sha256=sha(proposal),plan=plan,
                            expected_duration_seconds=expected,watchdog_seconds=7200,log_sha256=sha(log)))
    if emit_only:
        print('Two draft proposals emitted; not yet planned or ready');return
    import queue_runner as Q
    writes=sum(Q.W.WRITES['K1' if w.startswith('K1') else w] for w in Q.ORDER)*2
    free=shutil.disk_usage('/').free;assert free-writes>=25_000_000_000
    save(P/'evidence/queue-plans.json',dict(passed=True,device_executed=False,services_started=False,live_queue_changed=False,
        temporary_queue=True,records=records,build_receipt_sha256=sha(P/'build-receipt.json'),
        storage=dict(root_free_bytes=free,planned_write_bytes=writes,stop_floor_bytes=25_000_000_000)))
    print('Two temporary lane-A plans PASS; proposals unqueued')
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
