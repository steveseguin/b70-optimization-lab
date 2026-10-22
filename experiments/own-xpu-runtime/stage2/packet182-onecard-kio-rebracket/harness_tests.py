#!/usr/bin/env python3
"""Packet182 Python gate: the copied harness tests, against an unchanged packet176 baseline. CPU only.

packet176 sealed its v5 harness without a unit-test receipt; many inherited tests
(58v/58x/58aj screens: mapped/resident arms, older admission envelopes) no longer match
the harness that ran on the device on 2026-10-19. So the gate is differential:
the same discovery runs in this packet and in a scratch copy of packet176's working tree
(R/stage2/packet176-onecard-kernelio, all other entries symlinked), and
- every test failing here must also fail identically there (no regression from the copy);
- the packet182 additions (screen/test_mechanism_fill.py) and the unit-name test
  (screen/test_launch_unit.py, which binds the lanequeue unit to this packet) must pass;
- top-level test_kernelio_delta (native delta present, absent in the parent) must pass;
- chain/test_chain_gate.py (the +2% chain rule on retained real summaries) must pass.
Writes evidence/python-cpu-gates.json and evidence/python-cpu-gates.log.
"""
import json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
X = 'experiments/own-xpu-runtime'
SCRATCH = Path('/tmp/claude-1000/-home-steve/1df77db8-272b-4a21-9a32-d0349da3fe39/scratchpad')
LINE = re.compile(r'^(ERROR|FAIL): (\S+) \((\S+)\)', re.M)


def discover(start, pattern='test_*.py', names=None):
    argv = [sys.executable, '-B', '-m', 'unittest'] + (names if names else ['discover', '-s', str(start), '-p', pattern])
    cp = subprocess.run(argv, cwd=start, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=1800,
                        env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    out = cp.stdout + cp.stderr
    ran = re.search(r'Ran (\d+) tests', out)
    failing = sorted({f'{kind}: {m} ({c})' for kind, m, c in LINE.findall(out)})
    return dict(returncode=cp.returncode, tests=int(ran.group(1)) if ran else 0, failing=failing), out


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert shutil.disk_usage('/').free >= 27_000_000_000
    mine, log1 = discover(P / 'screen')
    fill, log2 = discover(P / 'screen', names=['test_mechanism_fill', 'test_launch_unit'])
    delta, log3 = discover(P, names=['test_kernelio_delta'])
    chain, log5 = discover(P / 'chain', names=['test_chain_gate'])
    base = Path(tempfile.mkdtemp(prefix='p182-harness-', dir=SCRATCH if SCRATCH.is_dir() else None))
    try:
        R = base / 'repo'
        for rel in (f'{X}/stage2', f'{X}/ops'):
            (R / rel).mkdir(parents=True)
            for e in (ROOT / rel).iterdir():
                if e.name not in ('packet176-onecard-kernelio', 'suite-inputs-20261012'):
                    (R / rel / e.name).symlink_to(e)
        shutil.copytree(ROOT / f'{X}/stage2/suite-inputs-20261012', R / f'{X}/stage2/suite-inputs-20261012')
        shutil.copytree(ROOT / f'{X}/stage2/packet176-onecard-kernelio', R / f'{X}/stage2/packet176-onecard-kernelio', symlinks=True,
                        ignore=shutil.ignore_patterns('__pycache__', 'preparation-sequence'))
        for e in ROOT.iterdir():
            if e.name not in ('experiments', '.git'):
                (R / e.name).symlink_to(e)
        for e in (ROOT / 'experiments').iterdir():
            if e.name != 'own-xpu-runtime':
                (R / 'experiments' / e.name).symlink_to(e)
        for e in (ROOT / X).iterdir():
            if e.name not in ('stage2', 'ops'):
                (R / X / e.name).symlink_to(e)
        theirs, log4 = discover(R / f'{X}/stage2/packet176-onecard-kernelio/screen')
    finally:
        shutil.rmtree(base, ignore_errors=True)
    rename = lambda s: s
    new_failures = sorted(set(map(rename, mine['failing'])) - set(theirs['failing']))
    (P / 'evidence').mkdir(exist_ok=True)
    log = P / 'evidence/python-cpu-gates.log'
    log.write_text('== packet182 screen discovery\n' + log1 + '\n== packet182 additions + unit name\n' + log2 +
                   '\n== packet182 top-level delta test\n' + log3 + '\n== packet182 chain rule tests\n' + log5 +
                   '\n== packet176 baseline (scratch copy) screen discovery\n' + log4)
    passed = (not new_failures and fill['returncode'] == 0 and fill['tests'] >= 4 and delta['returncode'] == 0
              and chain['returncode'] == 0 and chain['tests'] == 5
              and mine['tests'] == theirs['tests'] + 3)
    row = dict(schema='packet182.python-gates.v1', passed=passed, device_executed=False, rule=__doc__.strip().splitlines()[0],
               packet182_screen=mine, packet176_baseline_screen=theirs, new_failures=new_failures,
               added_tests_and_unit_name=fill, kernelio_delta=delta, chain_rule_tests=chain,
               inherited_stale_failures=len(mine['failing']), note='inherited stale tests fail identically on the unchanged packet176 harness; '
                                                                   'they are not device-path gates (packet176 sealed without them)')
    (P / 'evidence/python-cpu-gates.json').write_text(json.dumps(row, indent=2) + '\n')
    print(json.dumps(dict(passed=passed, mine=mine['tests'], theirs=theirs['tests'], new_failures=new_failures,
                          added=fill['returncode'] == 0, delta=delta['returncode'] == 0, chain=chain['returncode'] == 0)))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
