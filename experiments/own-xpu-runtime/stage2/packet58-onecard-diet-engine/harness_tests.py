#!/usr/bin/env python3
"""Packet58-onecard-diet-engine Python gate: the harness tests, differential against packet58-onecard-cache23's committed
gate receipt (the unchanged parent harness: evidence/python-cpu-gates.json, 113 screen tests, 2 inherited stale failures). CPU only.

- every test failing here must also fail identically in the parent receipt (no regression from this delta);
- the diet policy/decision tests (screen/test_capacity.py, test_async_policy.py, test_bracket.py incl. the gate-up boundary
  test, test_decision.py, test_launch_unit.py) must pass;
- the top-level delta test (test_dietengine_delta) and the root memory/admission tests must pass.
Writes evidence/python-cpu-gates.json and evidence/python-cpu-gates.log.
"""
import hashlib, json, os, re, shutil, subprocess, sys
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
PARENT_RECEIPT = P.parent / 'packet58-onecard-cache23/evidence/python-cpu-gates.json'
LINE = re.compile(r'^(ERROR|FAIL): (\S+) \((\S+)\)', re.M)


def failure_signatures(log):
    """Keep the reason as well as the test name when allowing inherited failures."""
    matches = list(LINE.finditer(log))
    rows = {}
    for i, match in enumerate(matches):
        block = log[match.end():matches[i + 1].start() if i + 1 < len(matches) else len(log)]
        exception = re.findall(r'^([\w.]+(?:Error|Exception):[^\n]*)$', block, re.M)
        reason = exception[0] if exception else '<missing exception signature>'
        for packet in (str(P), str(P.parent / 'packet58-onecard-cache23')):
            reason = reason.replace(packet, '<packet>')
        rows.setdefault(match.group(3), set()).add(match.group(1) + ': ' + reason)
    return {name: sorted(reasons) for name, reasons in rows.items()}


def discover(start, pattern='test_*.py', names=None, cwd=None):
    argv = [sys.executable, '-B', '-m', 'unittest'] + (names if names else ['discover', '-s', str(start), '-p', pattern])
    cp = subprocess.run(argv, cwd=cwd or start, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=1800,
                        env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    out = cp.stdout + cp.stderr
    ran = re.search(r'Ran (\d+) tests', out)
    failing = sorted({f'{kind}: {m} ({c})' for kind, m, c in LINE.findall(out)})
    return dict(returncode=cp.returncode, tests=int(ran.group(1)) if ran else 0, failing=failing), out


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert shutil.disk_usage('/').free >= 27_000_000_000
    mine, log1 = discover(P / 'screen')
    added, log2 = discover(P / 'screen', names=['test_capacity', 'test_decision', 'test_launch_unit', 'test_bracket', 'test_async_policy'])
    delta, log3 = discover(P, names=['test_dietengine_delta', 'test_memory_plan', 'test_resident', 'test_memory_sensor'])
    parent = json.loads(PARENT_RECEIPT.read_text())
    parent_log_path = PARENT_RECEIPT.with_suffix('.log')
    parent_log = parent_log_path.read_text().split('\n== policy/decision/unit tests', 1)[0]
    theirs = parent['packet58c23_screen']
    strip = lambda s: s.split(' (')[1].rstrip(')') if ' (' in s else s
    new_failures = sorted(set(map(strip, mine['failing'])) - set(map(strip, theirs['failing'])))
    fixed = sorted(set(map(strip, theirs['failing'])) - set(map(strip, mine['failing'])))
    signatures = failure_signatures(log1)
    parent_signatures = failure_signatures(parent_log)
    changed_reasons = {name: dict(actual=reasons, parent=parent_signatures.get(name))
                       for name, reasons in signatures.items() if reasons != parent_signatures.get(name)}
    (P / 'evidence').mkdir(exist_ok=True)
    log = P / 'evidence/python-cpu-gates.log'
    log.write_text('== packet58-onecard-diet-engine screen discovery\n' + log1 + '\n== policy/decision/unit tests\n' + log2 + '\n== top-level delta + memory tests\n' + log3)
    passed = (not new_failures and not changed_reasons and added['returncode'] == 0 and added['tests'] >= 20 and delta['returncode'] == 0 and mine['tests'] > theirs['tests'])
    row = dict(schema='packet58dietengine.python-gates.v1', passed=passed, device_executed=False, rule=__doc__.strip().splitlines()[0],
               packet58de_screen=mine, parent_receipt=dict(path=str(PARENT_RECEIPT.relative_to(ROOT)), tests=theirs['tests'], failing=theirs['failing']),
               new_failures=new_failures, fixed_vs_parent=fixed, failure_signatures=signatures, parent_failure_signatures=parent_signatures,
               changed_failure_reasons=changed_reasons, parent_log_sha256=hashlib.sha256(parent_log_path.read_bytes()).hexdigest(),
               policy_decision_unit_tests=added, delta_and_memory_tests=delta,
               inherited_stale_failures=len(mine['failing']),
               note='remaining failures fail identically on the unchanged parent harness (cache23 receipt); they are not device-path gates')
    (P / 'evidence/python-cpu-gates.json').write_text(json.dumps(row, indent=2) + '\n')
    print(json.dumps(dict(passed=passed, mine=mine['tests'], mine_failing=len(mine['failing']), theirs=theirs['tests'], theirs_failing=len(theirs['failing']),
                          new_failures=new_failures, changed_failure_reasons=changed_reasons, fixed=fixed, added=added['returncode'] == 0, added_tests=added['tests'], delta=delta['returncode'] == 0, delta_tests=delta['tests'])))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
