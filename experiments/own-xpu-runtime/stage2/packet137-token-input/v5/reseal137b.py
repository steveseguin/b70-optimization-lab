"""Owner-authorized report-only reseal; no model reads, build or device work.

Run --prepare before planning and --finish afterward. This refreshes only
explicit packet137 report dependencies, retaining original receipts verbatim.
"""
import hashlib
import gzip
import json
import subprocess
import sys
from pathlib import Path
import common as C

P = Path(__file__).resolve().parent
E = P/'evidence/reseal137b'
FILES = ('screen.py','packet137_report.py','cpu_seal.py','bracket_job.py','test_v5.py',
         'preplan.py','readiness.py','report_gate.py','reseal137b.py','plan137b.py')


def save(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row, indent=2)+'\n')


def key(path):
    return str(path.relative_to(C.ROOT))


def main():
    from conditions import cpu_gate
    cpu_gate()
    E.mkdir(exist_ok=True)
    # Only these top-level metadata receipts may change; device evidence stays frozen.
    receipts = [p for p in sorted((P/'evidence').glob('*.json'))
                if not p.name.startswith('report137b') and isinstance(C.read(p).get('sources'), dict)]
    seals = [P/'lineage/screen-seal.json', P/'placement-validation/wrapper-seal.json']
    before = E/'before.json.gz'
    original = json.loads(gzip.decompress(before.read_bytes())) if before.exists() else {}
    legacy = E/'before.json'
    if legacy.exists():
        original.update(C.read(legacy))
    for p in receipts+seals:
        if key(p) not in original:
            original[key(p)] = subprocess.run(['git','show','HEAD:'+key(p)], check=True,
                capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
    before.write_bytes(gzip.compress(json.dumps(original, sort_keys=True).encode(), mtime=0))
    assert json.loads(gzip.decompress(before.read_bytes())) == original
    if legacy.exists():
        legacy.unlink()  # Exact verified replacement of this task's scratch snapshot.
    historical_queue = 'experiments/own-xpu-runtime/ops/lane-queue/lanequeue.py'
    historical_hash = 'b9dd0dd09d6d0daebc297a6a7047be6c7e06fa737fe2d578840308c4d45aa602'
    snapshot = E/('lanequeue-'+historical_hash+'.py')
    if not snapshot.exists():
        content = subprocess.run(['git','show','981a673c8:'+historical_queue], check=True,
            capture_output=True, stdin=subprocess.DEVNULL).stdout
        assert hashlib.sha256(content).hexdigest() == historical_hash
        snapshot.write_bytes(content)
    assert C.sha(snapshot) == historical_hash
    proposals = [P.parents[2]/'ops/lane-queue'/('proposed-p137-'+n+'-B.txt') for n in ('smoke','v5')]
    changed = {key(P/n): C.sha(P/n) for n in FILES}
    changed.update({key(p):C.sha(p) for p in proposals})
    changed.update({key(P/'evidence'/n):C.sha(P/'evidence'/n) for n in
                    ('report137b-gate.json','report137b-collision-audit.json')})
    old_compare = key(P/'compare.py')
    annotation = dict(scope='report import/dispatch only; inherited numerical checks retained, not rerun',
                      before_receipts=key(before), report_gate=key(P/'evidence/report137b-gate.json'))
    rows = {key(p):C.read(p) for p in receipts+seals}
    if '--finish' in sys.argv:
        plan = C.read(P/'evidence/report137b-plans.json')
        rows[key(P/'evidence/queue-plan.json')] = dict(
            passed=plan['passed'], device_executed=False, live_queue_modified=False,
            packet_plan_passed=plan['packet_plan_passed'],
            operational_admission_synthetic=True,
            sources={key(P/'plan137b.py'):C.sha(P/'plan137b.py'),
                     key(P/'evidence/report137b-plans.json'):C.sha(P/'evidence/report137b-plans.json')},
            report137b_amendment=annotation,
            reason='current queue pin guard refuses inherited cross-packet pins' if not plan['passed'] else None)
        qualification = rows[key(P/'evidence/qualification.json')]
        qualification.update(passed=plan['passed'], cpu_preparation_ready=plan['passed'],
                             report_repair_passed=True, queue_pin_guard_passed=plan['passed'])
    # Source closures are a DAG. Update only reviewed local deltas, never unknown
    # mismatches or mutable external files. Four passes cover nested gate receipts.
    for _ in range(6):
        for path in receipts+seals:
            row = rows[key(path)]
            touched = False
            for field in ('sources','proposals'):
                mapping = row.get(field, {})
                if historical_queue in mapping:
                    assert mapping.pop(historical_queue) == historical_hash
                    mapping[key(snapshot)] = historical_hash
                    touched = True
                if old_compare in mapping:
                    del mapping[old_compare]
                    mapping[key(P/'packet137_report.py')] = changed[key(P/'packet137_report.py')]
                    touched = True
                for name in list(mapping):
                    if name in changed and mapping[name] != changed[name]:
                        mapping[name] = changed[name]
                        touched = True
            if path in seals:
                row['sources'].update({key(P/n):changed[key(P/n)] for n in FILES})
                row['sources'].update({key(P/'evidence'/n):changed[key(P/'evidence'/n)] for n in
                                     ('report137b-gate.json','report137b-collision-audit.json')})
                touched = True
            if path.name == 'qualification.json':
                row['sources'][key(P/'evidence/report137b-gate.json')] = changed[key(P/'evidence/report137b-gate.json')]
                row['screen_seal_sha256'] = C.sha(seals[0])
                touched = True
            if touched or row.get('report137b_amendment'):
                row['report137b_amendment'] = annotation
                save(path, row)
            changed[key(path)] = C.sha(path)
    assert C.read(seals[0]) == C.read(seals[1])
    for path in receipts+seals:
        row = C.read(path)
        if row.get('sources'):
            C.verify_map(C.ROOT, row['sources'])
    # No table, oracle payload or model shard is opened here.
    save(E/'receipt.json', dict(passed=True, device_executed=False, model_reads=False,
        native_rebuilt=False, inherited_checks_rerun=False, source_maps_verified=True,
        before_sha256=C.sha(before), files={key(p):C.sha(p) for p in receipts+seals},
        report_gate_sha256=C.sha(P/'evidence/report137b-gate.json')))
    print('PASS report-only reseal and source maps; full runtime/table/oracle admission remains mandatory')


if __name__ == '__main__':
    main()
