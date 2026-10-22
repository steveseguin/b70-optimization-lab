#!/usr/bin/env python3
"""Packet188 sealed-state checks: entry/report gates, private-copy queue plan, pin guard (no waiter: a measurement).

Runs after package_rows.py, on the sealed state, so the plan and rehearsals see exactly
what a window would launch. CPU only; never queues, never launches, never touches PAUSE files.
  v5/entry_gate.py           real closed entry, unit gates, both native exec boundaries (A and B)
  v5/launch_limit_gate.py    real rank exec boundaries keep every inherited getrlimit
  v5/worker_gate.py          every request of the three packet188 rows + error teardown in CPU scratch
  v5/report_gate.py          real bracket_job report path, three rows, both lanes
  v5/p188_v5_queue_plan.py   lanequeue.py plan --lane B on a PRIVATE copy (queue-B.txt = the
                             proposal) + ops/rehearse_entry.py --report --json on the proposal
  v5/pin_gate.py             live pin guard check_job on all three rows
Writes v5/evidence/check-queue-rows.json.
"""
import hashlib,json,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];V5=HERE/'v5'
STEPS=[('entry',V5/'entry_gate.py'),('launch-limits',V5/'launch_limit_gate.py'),('worker',V5/'worker_gate.py'),('report',V5/'report_gate.py'),
       ('queue-plan',V5/'p188_v5_queue_plan.py'),('pin-guard',V5/'pin_gate.py')]
RECEIPTS={'entry':'entry-gate.json','launch-limits':'launch-limits.json','worker':'worker-gate.json','report':'report-gate.json',
          'queue-plan':'queue-plan.json','pin-guard':'pin-guard.json'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    sys.path.insert(0,str(V5))
    from cpu_seal import verify
    verify()
    rows=[]
    for name,script in STEPS:
        t=time.monotonic()
        r=subprocess.run([sys.executable,'-B',str(script)],cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=3600)
        log=V5/'evidence'/f'check-{name}.log';log.write_text(r.stdout+r.stderr)
        if r.returncode:sys.exit(f'{name} failed (see {log.relative_to(ROOT)})')
        receipt=V5/'evidence'/RECEIPTS[name];row=json.loads(receipt.read_text());assert row['passed'] is True and row['device_executed'] is False,name
        rows.append(dict(step=name,seconds=round(time.monotonic()-t,1),receipt=str(receipt.relative_to(ROOT)),receipt_sha256=sha(receipt)))
        print('PASS',name,flush=True)
    plan=(V5/'evidence/plan-B.log').read_text().splitlines()
    (V5/'evidence/check-queue-rows.json').write_text(json.dumps(dict(passed=True,device_executed=False,queued=False,steps=rows,
        private_plan_lines=plan),indent=1)+'\n')
if __name__=='__main__':main()
