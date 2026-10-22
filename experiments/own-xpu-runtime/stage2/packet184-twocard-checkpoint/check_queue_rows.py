#!/usr/bin/env python3
"""Packet184 sealed-state queue checks (CPU only; never queues, never launches, no PAUSE files).

Runs after package_rows.py on the sealed state, so the plan sees exactly what a window would launch:
  1 private-copy plan   ops/lane-queue/*.py copied into a temporary directory whose queue-B.txt is the
                        proposal; `lanequeue.py plan --lane B --directory TMP` (the live planner code):
                        pin guard, CPU --plan of checkpoint_job.py, storage and host admission, both rows
  2 entry rehearsal     ops/rehearse_entry.py PROPOSAL --report --json (loader/argument checks of the
                        declared host-only binaries; the device binary is never executed)
  3 pin guard           pin_guard.check_job on both rows (0 cross-packet mutable pins required)
Refuses a missing/stale seal or an existing READY. Writes v5/evidence/{plan-B.log,queue-plan.json,
rehearse.log,rehearse.json,pin-guard.json,check-queue-rows.json}.
"""
import hashlib, importlib.util, json, shutil, subprocess, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
V5 = HERE / 'v5'
EV = V5 / 'evidence'
LQ = HERE.parents[1] / 'ops/lane-queue'
NAME = 'proposed-p184-two-card-B.txt'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rel(p):
    return str(Path(p).relative_to(ROOT))


def save(name, row):
    (EV / name).write_text(json.dumps(row, indent=1) + '\n')


def main():
    if (HERE / 'READY-FOR-DEVICE.json').exists():
        sys.exit('READY-FOR-DEVICE.json exists; withdraw it before re-checking')
    sys.path.insert(0, str(V5))
    from cpu_seal import verify
    seal = verify()
    pkg = json.loads((EV / 'package-rows.json').read_text())
    live, mirror = LQ / NAME, HERE / 'proposals' / NAME
    assert sha(live) == sha(mirror) == pkg['proposal_sha256'] and pkg['cpu_seal_sha256'] == sha(V5 / 'cpu-seal.json'), 'stale package'
    text = live.read_text()
    rows = [json.loads(l) for l in text.splitlines() if l.strip() and not l.lstrip().startswith('#')]
    steps = []
    # 1 private-copy plan with the live planner code
    queue_code = {p.name: sha(p) for p in LQ.glob('*.py')}
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='p184-plan-') as d:
        tmp = Path(d)
        for src in LQ.glob('*.py'):
            shutil.copy2(src, tmp / src.name)
        (tmp / 'queue-B.txt').write_text(text)
        log = EV / 'plan-B.log'
        with log.open('w') as out:
            r = subprocess.run([sys.executable, '-B', str(LQ / 'lanequeue.py'), 'plan', '--lane', 'B', '--directory', str(tmp)],
                               cwd=ROOT, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, timeout=1200)
    plan_lines = [json.loads(l) for l in log.read_text().splitlines() if l.startswith('{')]
    assert r.returncode == 0 and len(plan_lines) == 2 and all(p.get('plan') == 'passed' for p in plan_lines), log.read_text()[-6000:]
    assert {p['name'] for p in plan_lines} == {row['name'] for row in rows}
    assert {p.name: sha(p) for p in LQ.glob('*.py')} == queue_code, 'queue code changed during planning'
    save('queue-plan.json', dict(passed=True, device_executed=False, live_queue_modified=False, queued=False, proposal=rel(live), sha256=sha(live),
                                 log=rel(log), log_sha256=sha(log), rows=plan_lines, seconds=round(time.monotonic() - started, 1),
                                 planner=rel(LQ / 'lanequeue.py'), planner_digest=sha(LQ / 'lanequeue.py')))   # observed, not pinned (ops code is not packet-owned)
    steps.append(dict(step='private-copy lanequeue.py plan --lane B', passed=True, rows=[(p['name'], p['plan']) for p in plan_lines]))
    print('PASS private-copy plan --lane B', [p['name'] for p in plan_lines], flush=True)
    # 2 entry rehearsal (declared host-only binaries; device binary never executed)
    r = subprocess.run([sys.executable, '-B', str(LQ.parent / 'rehearse_entry.py'), str(live), '--report', '--json'], cwd=ROOT,
                       stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=1200)
    (EV / 'rehearse.log').write_text(r.stdout + r.stderr)
    try:
        rehearsal = json.loads(r.stdout)
    except ValueError:
        rehearsal = dict(passed=False, unparsed=True)
    save('rehearse.json', dict(rehearsal, returncode=r.returncode, device_executed=False))
    steps.append(dict(step='ops/rehearse_entry.py --report', passed=r.returncode == 0 and rehearsal.get('passed') is True, returncode=r.returncode,
                      receipt=rel(EV / 'rehearse.json')))
    print(('PASS' if steps[-1]['passed'] else 'NOT PASSED'), 'entry rehearsal', flush=True)
    # 3 live pin guard on both rows
    spec = importlib.util.spec_from_file_location('p184_pin_guard_live', LQ / 'pin_guard.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    checks = [m.check_job(row) for row in rows]
    assert all(c['passed'] for c in checks)
    save('pin-guard.json', dict(passed=True, device_executed=False, rows=[dict(job=row['name'], **c) for row, c in zip(rows, checks)]))
    steps.append(dict(step='pin_guard.check_job', passed=True, pins=[c.get('pins') for c in checks]))
    print('PASS pin guard', [c.get('pins') for c in checks], flush=True)
    save('check-queue-rows.json', dict(passed=all(s['passed'] for s in steps), device_executed=False, queued=False, cpu_seal_sha256=sha(V5 / 'cpu-seal.json'),
                                       binary_sha256=seal['binary_sha256'], steps=steps,
                                       receipts={rel(EV / n): sha(EV / n) for n in ('plan-B.log', 'queue-plan.json', 'rehearse.json', 'pin-guard.json')}))
    if not all(s['passed'] for s in steps):
        sys.exit('check_queue_rows: a step did not pass (see v5/evidence/check-queue-rows.json)')


if __name__ == '__main__':
    main()
