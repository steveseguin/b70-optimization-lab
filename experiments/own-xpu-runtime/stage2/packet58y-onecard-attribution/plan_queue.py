"""Plan the ordered 58x/58y batch on temporary copies; never queue live work."""
import argparse,json,resource,shutil,subprocess,sys,tempfile
from pathlib import Path
from build_engine import P,ROOT,limits,save,sha
QUEUE=P.parents[1]/'ops/lane-queue'
PROPOSAL=QUEUE/'proposed-p58y-attrib-A.txt'
PREDECESSORS=('proposed-p58x-smoke-A.txt','proposed-p58x-v5-A.txt')

def job():
    library=json.loads((P/'library-path.json').read_text())['LD_LIBRARY_PATH']
    return dict(name='packet58y-attrib-A',lane='A',argv=['/usr/bin/python3','-B',str((P/'queue_runner.py').relative_to(ROOT)),
        '--arm','attrib','--output',str(P/'evidence/card0-attribution-a/attrib'),
        '--fault-review','{REVIEW}','--library-path',library,'--authorized-device-window'],
        env_extra={},review=str((P/'fault_review.py').relative_to(ROOT)),
        depends_on=['packet58x-smoke-A','packet58x-v5-A'],
        plan=dict(scope='whole-host',batch='packet58x-smoke-bracket-then-58y',
                  same_hold_required=True,standalone_hold_allowed=False,
                  expected_duration_seconds=[600,900],watchdog_seconds=7200,
                  host_required_available_bytes=95_435_761_152))

def emit():
    limits()
    raw=('# CPU proposal only. DO NOT QUEUE from this preparation.\n'
         '# Card 0 / lane A / WHOLE HOST. Mandatory coordinator batch, in this order:\n'
         '# packet58x-smoke-A -> packet58x-v5-A -> packet58y-attrib-A.\n'
         '# SAME continuous whole-host hold and PAUSE-B; no intervening job or standalone 58y hold.\n'
         '# 12 fixed prompts x 128 max; one load, overlap cache, every token checked against packet49.\n'
         '# Expected <=900 seconds including K1 and gaps; watchdog 7200 >=4x.\n'
         '# Recorded oneAPI path; closed environment; screen-<job>; measured 58u admission.\n'+json.dumps(job())+'\n')
    if PROPOSAL.exists():assert PROPOSAL.read_text()==raw,'proposal changed'
    else:PROPOSAL.write_text(raw)
    return raw

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--emit-only',action='store_true');args=ap.parse_args()
    raw=emit()
    if args.emit_only:return
    import queue_runner as Q
    Q.W.build_gate()
    records=[];pins={}
    with tempfile.TemporaryDirectory(prefix='packet58y-batch-plan-') as directory:
        temporary=Path(directory)
        ordered=[]
        for name in PREDECESSORS:
            source=QUEUE/name;pins[str(source.relative_to(ROOT))]=sha(source)
            ordered.extend(json.loads(line) for line in source.read_text().splitlines() if line.strip() and not line.startswith('#'))
        ordered.append(job())
        assert [r['name'] for r in ordered]==['packet58x-smoke-A','packet58x-v5-A','packet58y-attrib-A']
        (temporary/'queue-A.txt').write_text('\n'.join(map(json.dumps,ordered))+'\n')
        # Full batch planner invokes all three existing --plan entry points.
        command=[sys.executable,'-B',str(QUEUE/'lanequeue.py'),'plan','--lane','A','--directory',directory]
        result=subprocess.run(command,cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=360)
        log=P/'evidence'/('queue-plan-batch-'+str(1+len(list((P/'evidence').glob('queue-plan-batch-*.log'))))+'.log');log.write_text(result.stdout+result.stderr)
        assert result.returncode==0,log.read_text()[-6000:]
        plans=[json.loads(line) for line in result.stdout.splitlines()]
        assert len(plans)==3 and all(r['plan']=='passed' for r in plans)
        records=plans
    free=shutil.disk_usage('/').free
    writes=sum(Q.W.WRITES['K1' if n.startswith('K1') else n] for n in Q.ORDER)
    predecessor_plan=QUEUE.parents[1]/'stage2/packet58x-cache-capacity/evidence/queue-plans.json'
    predecessor_writes=json.loads(predecessor_plan.read_text())['storage']['planned_write_bytes']
    assert predecessor_writes>=2*writes
    assert free-writes-predecessor_writes>=25_000_000_000
    save(P/'evidence/queue-plans.json',dict(passed=True,device_executed=False,services_started=False,live_queue_changed=False,
        temporary_queue=True,records=records,proposal=str(PROPOSAL.relative_to(ROOT)),proposal_sha256=sha(PROPOSAL),
        predecessor_proposals=pins,same_hold_required=True,standalone_hold_allowed=False,
        order=[r['name'] for r in ordered],expected_duration_seconds=[600,900],watchdog_seconds=7200,
        build_receipt_sha256=sha(P/'build-receipt.json'),storage=dict(root_free_bytes=free,planned_write_bytes=writes,predecessor_write_bytes=predecessor_writes,batch_write_bytes=writes+predecessor_writes,stop_floor_bytes=25_000_000_000)))
    print('Ordered temporary 58x smoke / 58x bracket / 58y attribution batch PASS; unqueued')
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
