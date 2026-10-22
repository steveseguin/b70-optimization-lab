#!/usr/bin/env python3
"""Packet182 CPU gates in their run order (CPU only; never a device binary beyond --help).

  nice -n 19 taskset -c 8-15,24-31 python3 -B gates.py --step <name> < /dev/null
  nice -n 19 taskset -c 8-15,24-31 python3 -B gates.py --check       < /dev/null   (verify every receipt)

Order (after copy_packet.py + rebind_pins.py + plan_queue.py --emit-only):
  k1          build_k1_wrapper.py            evidence/k1-wrapper.json
  inherited   inherited_gates.py             evidence/inherited-binary-gates.json
  preparation preparation182.py              evidence/preparation.json (+ preparation-sequence/)
  arguments   screen/argument_gate.py        screen/evidence/argument-gate.json
  analyzer    analyzer_gate.py               evidence/analyzer-real-parent.json
  fill        fill_price.py                  evidence/fill-lever-price.json
  python      harness_tests.py               evidence/python-cpu-gates.json
  drain       scripts/check_drain_fix.py     evidence/drain-fix.json
  chain       chain/rehearse_chain.py        evidence/chain-rehearsal.json
  waiter      chain/rehearse_waiter.py       evidence/waiter-rehearsal.json (dry run of chain/p182-win.sh)
Then package_rows.py (seal + proposal), check_queue_rows.py (plan + rehearse + pins),
final_checks.py, final_checks.py --ready.
"""
import argparse, hashlib, json, os, subprocess, sys
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
STEPS = {
    'k1': (['build_k1_wrapper.py'], 'evidence/k1-wrapper.json'),
    'inherited': (['inherited_gates.py'], 'evidence/inherited-binary-gates.json'),
    'preparation': (['preparation182.py'], 'evidence/preparation.json'),
    'arguments': (['screen/argument_gate.py'], 'screen/evidence/argument-gate.json'),
    'analyzer': (['analyzer_gate.py'], 'evidence/analyzer-real-parent.json'),
    'fill': (['fill_price.py'], 'evidence/fill-lever-price.json'),
    'python': (['harness_tests.py'], 'evidence/python-cpu-gates.json'),
    'drain': (None, 'evidence/drain-fix.json'),
    'chain': (['chain/rehearse_chain.py'], 'evidence/chain-rehearsal.json'),
    'waiter': (['chain/rehearse_waiter.py'], 'evidence/waiter-rehearsal.json'),
}


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def drain():
    cp = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/check_drain_fix.py'), str(P.relative_to(ROOT))], cwd=ROOT,
                        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=600)
    lines = [s for s in cp.stdout.splitlines() if s.strip()]
    row = dict(schema='packet182.drain-fix.v1', passed=cp.returncode == 0 and any('0 UNFIXED' in s for s in lines), device_executed=False,
               command=['python3', '-B', 'scripts/check_drain_fix.py', str(P.relative_to(ROOT))], returncode=cp.returncode, output=lines,
               checker_sha256=sha(ROOT / 'scripts/check_drain_fix.py'))
    (P / 'evidence/drain-fix.json').write_text(json.dumps(row, indent=2) + '\n')
    return row['passed']


def check():
    rows = {}
    for name, (_, receipt) in STEPS.items():
        r = json.loads((P / receipt).read_text())
        rows[name] = dict(receipt=receipt, passed=r.get('passed') is True, device_executed=r.get('device_executed'))
    ok = all(v['passed'] and v['device_executed'] is False for v in rows.values())
    print(json.dumps(dict(passed=ok, gates=rows), indent=1))
    return 0 if ok else 1


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--step', choices=STEPS)
    g.add_argument('--check', action='store_true')
    a = ap.parse_args()
    if a.check:
        return check()
    if a.step == 'drain':
        return 0 if drain() else 1
    script = STEPS[a.step][0][0]
    return subprocess.run([sys.executable, '-B', str(P / script)], cwd=(P / script).parent, stdin=subprocess.DEVNULL).returncode


if __name__ == '__main__':
    raise SystemExit(main())
