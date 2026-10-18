#!/usr/bin/env python3
"""Seal only the lane wrapper using mock CPU checks; no model execution."""
import argparse
from pathlib import Path
import subprocess
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
from common import ROOT, HERE, read, require, sha, save, verify_map
from conditions import cpu_gate
import cpu_seal as parent

Q = Path(__file__).resolve().parent
SEAL = Q / 'wrapper-seal.json'


def sources():
    paths = sorted(Q.glob('*.py')) + sorted(Q.glob('jobs-*.txt'))
    return {str(p.relative_to(ROOT)): sha(p) for p in paths}


def verify():
    parent.verify()
    row = read(SEAL)
    require(row.get('passed') is True and row.get('device_executed') is False, 'quick CPU seal missing')
    require(row['sources'] == sources(), 'quick wrapper changed; new seal required')
    require(row['parent_wrapper_sha256'] == sha(parent.ARTIFACTS / 'wrapper-seal.json'), 'parent seal changed')
    verify_map(Q, row['artifacts'])
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--verify', action='store_true')
    args = ap.parse_args()
    cpu_gate()
    if not args.verify:
        require(not SEAL.exists(), 'never overwrite a quick wrapper seal')
        parent.verify()
        closure = sources()
        for path in Q.glob('*.py'):
            compile(path.read_text(), str(path), 'exec')
        with (Q / 'cpu-tests.log').open('w') as log:
            subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(Q),
                            '-p', 'test_quick.py', '-v'], check=True, stdin=subprocess.DEVNULL,
                           stdout=log, stderr=subprocess.STDOUT)
        require(sources() == closure, 'wrapper changed during checks')
        save(SEAL, dict(schema='packet67.quick-wrapper-seal.v1', passed=True, device_executed=False,
                        sources=closure, parent_wrapper_sha256=sha(parent.ARTIFACTS / 'wrapper-seal.json'),
                        artifacts={'cpu-tests.log': sha(Q / 'cpu-tests.log')},
                        cpu_model_executed=False, device_quality='pending', device_speed='unmeasured'))
    verify()
    print('PASS: original wrapper and quick lane seal; no device or CPU model executed')


if __name__ == '__main__':
    main()
