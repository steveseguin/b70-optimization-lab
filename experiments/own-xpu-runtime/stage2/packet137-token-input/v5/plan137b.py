"""Rehearse fresh B proposals on a temporary queue; never queue a job.

The packet's real --plan and the real queue planner run with only full-table
rehashing and oracle payload admission replaced by retained receipts. This is
a model-free CPU rehearsal, not device admission. Production checks stay intact.
"""
import json
import gzip
import subprocess
import sys
import tempfile
from pathlib import Path
import common as C

P = Path(__file__).resolve().parent
QUEUE = P.parents[2]/'ops/lane-queue'


def proposals():
    rows = []
    for kind, leaf in [('smoke','smoke'), ('bracket','v5')]:
        path = QUEUE/f'proposed-p137-{leaf}-B.txt'
        row = C.read(path)
        row['name'] = 'packet137b-'+kind+'-B'
        row['argv'][row['argv'].index('--output')+1] = str(P/'evidence'/f'device-{leaf}-137b-B')
        if kind == 'bracket':
            row['depends_on'] = ['packet137b-smoke-B']
        rows.append((path, row))
    return rows


def invoke(command, **kwargs):
    # Only the registered packet entry's explicit --plan may run.
    assert command[:3] == ['/usr/bin/python3','-B',str((P/'bracket_job.py').relative_to(C.ROOT))]
    assert command[-1] == '--plan'
    code = '''import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import cpu_seal, bracket_job
row=cpu_seal.read(Path(sys.argv[1])/'lineage/screen-seal.json')
original_sha=cpu_seal.sha
table=Path(row['table']['path'])
cpu_seal.sha=lambda path: row['table']['sha256'] if Path(path)==table else original_sha(path)
cpu_seal.oracle=lambda: row['oracle']
raise SystemExit(bracket_job.main(sys.argv[2:]))
'''
    result = subprocess.run(['/usr/bin/python3','-B','-c',code,str(P),*command[3:]], **kwargs)
    if result.returncode:
        raise ValueError(result.stderr[-4000:])
    return result


def main():
    from conditions import cpu_gate
    cpu_gate()
    rows = proposals()
    if '--write' in sys.argv:
        # Called only after a successful rehearsal; write exactly its reviewed rows.
        receipt = C.read(P/'evidence/report137b-plans.json')
        assert receipt['packet_plan_passed'] and receipt['proposals'] == [r for _,r in rows]
        for path,row in rows:
            path.write_text(json.dumps(row)+'\n')
        return
    sys.path.insert(0,str(QUEUE))
    import lanequeue
    plans = []
    with tempfile.TemporaryDirectory(prefix='packet137b-queue-') as tmp:
        path = Path(tmp)/'queue-B.txt'
        path.write_text(''.join(json.dumps(r)+'\n' for _,r in rows))
        for line in path.read_text().splitlines():
            job = lanequeue.validate(json.loads(line),'B')
            ldp = C.read(P/'launch-environment.json')['LD_LIBRARY_PATH']
            try:
                plan = lanequeue.plan_job(job, ldp, invoke=invoke)
            except lanequeue.pin_guard.PinRefusal as error:
                refusal = P/'evidence'/('report137b-pin-refusal-'+job['name']+'.json.gz')
                raw = json.dumps(error.receipt, indent=2).encode()
                refusal.write_bytes(gzip.compress(raw, mtime=0))
                assert gzip.decompress(refusal.read_bytes()) == raw
                plan = dict(name=job['name'], plan='refused',
                    pin_error_count=len(error.receipt['errors']), first_errors=error.receipt['errors'][:8],
                    refusal=dict(path=str(refusal.relative_to(C.ROOT)), sha256=C.sha(refusal)))
            # Independently rehearse the packet plan after retaining any queue
            # refusal. This does not override or claim to pass that guard.
            command = job['argv'][:]
            index = command.index('--fault-review')
            del command[index:index+2]
            command.remove('--authorized-device-window')
            result = invoke(command+['--plan'], cwd=C.ROOT, env=lanequeue.closed_env(ldp),
                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)
            metadata = json.loads(result.stdout)
            assert metadata['device_executed'] is False
            plan['packet_plan_passed'] = True
            plans.append(plan)
    C.save(P/'evidence/report137b-plans.json', dict(passed=all(r['plan']=='passed' for r in plans),
        packet_plan_passed=True, device_executed=False, live_queue_modified=False,
        model_reads=False, operational_admission_synthetic=True,
        retained_checks=['projection table hash','complete oracle payload validation'],
        production_checks_unchanged=True, proposals=[r for _,r in rows], plans=plans))
    print('Packet plans PASS; queue plans: '+', '.join(r['plan'] for r in plans)+'; nothing queued')


if __name__ == '__main__':
    main()
