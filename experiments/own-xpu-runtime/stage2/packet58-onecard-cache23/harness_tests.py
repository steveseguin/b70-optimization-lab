#!/usr/bin/env python3
"""Packet58-cache23 Python gate: the harness tests, differential against an unchanged packet182 baseline. CPU only.

Inherited stale tests of the 58v/58x/58aj screens fail identically on the unchanged packet182 harness
(packet182's gate carried 5 such failures; its device run never read them). The gate is differential:
the same discovery runs here and in a scratch copy of packet182's committed tree, and
- every test failing here must also fail identically there (no regression from this delta);
- the packet58-cache23 policy/decision tests (screen/test_capacity.py rewritten, screen/test_decision.py,
  screen/test_launch_unit.py) must pass; the stale test_capacity/test_bracket/test_async_policy failures
  of packet182 must be FIXED here (they were rewritten for the new policy), so fewer failures than the baseline;
- the top-level delta test (test_cache23_delta) and the root memory/admission tests must pass.
Writes evidence/python-cpu-gates.json and evidence/python-cpu-gates.log.
"""
import json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
X = 'experiments/own-xpu-runtime'
PARENT = 'packet182-onecard-kio-rebracket'
SCRATCH = Path('/tmp/claude-1000/-home-steve/1df77db8-272b-4a21-9a32-d0349da3fe39/scratchpad')
LINE = re.compile(r'^(ERROR|FAIL): (\S+) \((\S+)\)', re.M)
EXPECTED_FIXED = {'test_capacity.Capacity.test_fixed_maintenance_and_capacity_rows', 'test_bracket.SummaryTests.test_all60_actual_oracle_and_metrics',
                  'test_async_policy.AsyncPolicy.test_smoke_and_bracket_dimensions'}


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
    # root test_admission58e is the screen copy's stale twin (imports screen modules); the screen copy runs in the discovery above
    delta, log3 = discover(P, names=['test_cache23_delta', 'test_memory_plan', 'test_resident', 'test_memory_sensor'])
    base = Path(tempfile.mkdtemp(prefix='p58c23-harness-', dir=SCRATCH if SCRATCH.is_dir() else None))
    try:
        R = base / 'repo'
        for rel in (f'{X}/stage2', f'{X}/ops'):
            (R / rel).mkdir(parents=True)
            for e in (ROOT / rel).iterdir():
                if e.name not in (PARENT, 'suite-inputs-20261012'):
                    (R / rel / e.name).symlink_to(e)
        shutil.copytree(ROOT / f'{X}/stage2/suite-inputs-20261012', R / f'{X}/stage2/suite-inputs-20261012')
        raw = subprocess.run(['git', '-C', str(ROOT), 'archive', 'HEAD', f'{X}/stage2/{PARENT}'], stdin=subprocess.DEVNULL, capture_output=True, check=True).stdout
        import io, tarfile
        with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
            tar.extractall(R, filter='data')
        (R / f'{X}/stage2/{PARENT}/build').symlink_to(ROOT / f'{X}/stage2/{PARENT}/build')
        for e in ROOT.iterdir():
            if e.name not in ('experiments', '.git'):
                (R / e.name).symlink_to(e)
        for e in (ROOT / 'experiments').iterdir():
            if e.name != 'own-xpu-runtime':
                (R / 'experiments' / e.name).symlink_to(e)
        for e in (ROOT / X).iterdir():
            if e.name not in ('stage2', 'ops'):
                (R / X / e.name).symlink_to(e)
        theirs, log4 = discover(R / f'{X}/stage2/{PARENT}/screen')
    finally:
        shutil.rmtree(base, ignore_errors=True)
    strip = lambda s: s.split(' (')[1].rstrip(')') if ' (' in s else s
    new_failures = sorted(set(map(strip, mine['failing'])) - set(map(strip, theirs['failing'])))
    fixed = sorted(set(map(strip, theirs['failing'])) - set(map(strip, mine['failing'])))
    (P / 'evidence').mkdir(exist_ok=True)
    log = P / 'evidence/python-cpu-gates.log'
    log.write_text('== packet58-cache23 screen discovery\n' + log1 + '\n== policy/decision/unit tests\n' + log2 + '\n== top-level delta + memory tests\n' + log3 +
                   '\n== packet182 baseline (scratch git-archive copy) screen discovery\n' + log4)
    passed = (not new_failures and added['returncode'] == 0 and added['tests'] >= 20 and delta['returncode'] == 0
              and EXPECTED_FIXED <= set(fixed) and mine['tests'] >= theirs['tests'])
    row = dict(schema='packet58cache23.python-gates.v1', passed=passed, device_executed=False, rule=__doc__.strip().splitlines()[0],
               packet58c23_screen=mine, packet182_baseline_screen=theirs, new_failures=new_failures, fixed_vs_baseline=fixed,
               policy_decision_unit_tests=added, delta_and_memory_tests=delta, inherited_stale_failures=len(mine['failing']),
               note='remaining failures fail identically on the unchanged packet182 harness; they are not device-path gates')
    (P / 'evidence/python-cpu-gates.json').write_text(json.dumps(row, indent=2) + '\n')
    print(json.dumps(dict(passed=passed, mine=mine['tests'], mine_failing=len(mine['failing']), theirs=theirs['tests'], theirs_failing=len(theirs['failing']),
                          new_failures=new_failures, fixed=fixed, added=added['returncode'] == 0, added_tests=added['tests'], delta=delta['returncode'] == 0, delta_tests=delta['tests'])))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
