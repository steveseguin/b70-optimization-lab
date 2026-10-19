"""Prepare proposals and test TEMPORARY queues only; never edit a live queue."""
import json,resource,shutil,subprocess,sys,tempfile
from pathlib import Path
from build_engine import P,ROOT,limits,save,sha
QUEUE=P.parents[1]/'ops/lane-queue'
def documents():
    from launch_env import library_path
    library=library_path();assert library==json.loads((P/'library-path.json').read_text())['LD_LIBRARY_PATH']
    for arm,tag,expected in [('smoke','smoke',[600,900]),('p60fusion','v5',[1200,1800])]:
        record=dict(name='packet58aj-'+tag+'-A',lane='A',argv=['/usr/bin/python3','-B',str((P/'queue_runner.py').relative_to(ROOT)),
            '--cache-maintenance','overlap','--arm',arm,'--output',str(P/'evidence/card0-ports-a'/arm),
            '--fault-review','{REVIEW}','--library-path',library,'--authorized-device-window'],env_extra={},review=str((P/'fault_review.py').relative_to(ROOT)))
        record['plan']=dict(entry_rehearsal=dict(binaries=[dict(path=str((P/'build/device'/n).relative_to(ROOT)),sha256=sha(P/'build/device'/n)) for n in ('own-rt-iq3','p58-cache-fixtures')]))
        record['plan']['entry_rehearsal']['binaries'][1].update(args=['--help'],returncode=1,contains='K1 unknown option')
        text=('# Proposal only: one card (card 0), lane A, whole host; lane B must be drained.\n'
            '# Two K1 fixtures, one model load. Tile16, overlap, full BF16 KV, 48 layers, cache 21,552,729,600 bytes.\n'
            '# Smoke 12 x 64 full composition. V5 12 x 128 packet58ab/full/packet58ab/full/packet58ab; HC fusion always on.\n'
            '# A0 exact and reported; excluded only from speed/drift (p58wb). Both candidates must beat both warm controls by 2%; warm drift <=3%.\n'
            f'# Expected {expected[0]}-{expected[1]} seconds; watchdog 7200 seconds (>=4x). Host admission 98,990,252,032 bytes.\n'
            '# No queuing or device execution during preparation. READY must be the final content write.\n'+json.dumps(record)+'\n')
        yield arm,tag,expected,text

def main():
    limits();records=[]
    for arm,tag,expected,raw in documents():
        name='proposed-p58aj-'+tag+'-A.txt';local=P/'proposals'/name;external=QUEUE/name
        if '--emit-only' in sys.argv:
            local.parent.mkdir(exist_ok=True);local.write_text(raw);external.write_text(raw);continue
        assert local.read_text()==external.read_text()==raw
        with tempfile.TemporaryDirectory(prefix='p58ag-plan-') as directory:
            (Path(directory)/'queue-A.txt').write_text(raw)
            from ready_document import document
            prospective=Path(directory)/'READY-FOR-DEVICE.json';prospective.write_text(json.dumps(document()))
            code=('import sys,pathlib;sys.path.insert(0,sys.argv.pop(1));import lanequeue,pin_guard;'
                'target=pathlib.Path(sys.argv.pop(1));copy=pathlib.Path(sys.argv.pop(1));original=pin_guard.read_metadata;'
                'pin_guard.read_metadata=lambda p:copy.read_bytes() if p==target else original(p);'
                'paths=pin_guard.metadata_paths;pin_guard.metadata_paths=lambda packet,root:sorted(set(paths(packet,root)+([target] if packet==target.parent else [])));'
                'raise SystemExit(lanequeue.main())')
            cmd=[sys.executable,'-B','-c',code,str(QUEUE),str(P/'READY-FOR-DEVICE.json'),str(prospective),'plan','--lane','A','--directory',directory]
            r=subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True)
        log=P/'evidence'/('queue-plan-'+tag+'.log');log.write_text(r.stdout+r.stderr)
        assert r.returncode==0,log.read_text()[-6000:]
        plan=[json.loads(x) for x in r.stdout.splitlines()];assert len(plan)==1 and plan[0]['plan']=='passed'
        records.append(dict(arm=arm,proposal=str(local.relative_to(ROOT)),proposal_sha256=sha(local),coordinator_path=str(external.relative_to(ROOT)),plan=plan,expected_duration_seconds=expected,watchdog_seconds=7200,log_sha256=sha(log)))
    if '--emit-only' in sys.argv:print('Two unqueued proposals written; readiness pending');return
    free=shutil.disk_usage('/').free;writes=2*(2*128*1024**2+1024**3);assert free-writes>=25_000_000_000
    save(P/'evidence/queue-plans.json',dict(passed=True,device_executed=False,services_started=False,live_queue_changed=False,temporary_queue=True,prospective_ready_copy=True,records=records,build_receipt_sha256=sha(P/'build-receipt.json'),storage=dict(root_free_bytes=free,planned_write_bytes=writes,stop_floor_bytes=25_000_000_000)))
    print('Both temporary lane-A plans PASS; nothing queued')
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3));main()
