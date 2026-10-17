#!/usr/bin/env python3
"""Build Python in memory, run the small CPU fixture/checks, seal; never a device."""
import argparse
import subprocess
import sys
from pathlib import Path
from common import HERE, ROOT, P56, P58, D, S, SUPPORT, W, M, DISPATCH, read, require, save, sha
from conditions import cpu_gate
import fault_review


def sources():
    paths = set(HERE.glob('*.py'))
    paths.add(P56 / 'memory-plan.json')
    paths.add(HERE.parent / 'tp2_worker.py')  # unchanged reference used by the fixture
    paths.add(P58 / 'oracle-binding.json')
    paths.add(fault_review.DRIVER)
    paths.update(Path(module.__file__) for module in (D, D.CHECK, D.METRICS, S, SUPPORT, W, M, DISPATCH))
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}


def verify():
    row = read(HERE / 'wrapper-seal.json')
    require(row.get('passed') is True and row.get('device_executed') is False,
            'wrapper CPU seal missing or failed')
    require(row['sources'] == sources(), 'screen v2 source closure changed; CPU reseal required')
    for name, digest in row['artifacts'].items():
        require(sha(HERE / name) == digest, 'wrapper artifact changed: ' + name)
    require(sha(HERE / 'fixture-actual.bin') == sha(HERE / 'fixture-expected.bin'), 'wrapper byte fixture differs')
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--verify', action='store_true')
    args = ap.parse_args()
    cpu_gate()
    if args.verify:
        verify()
    else:
        require(not (HERE / 'wrapper-seal.json').exists(), 'never overwrite wrapper seal')
        for path in HERE.glob('*.py'):
            compile(path.read_text(), str(path), 'exec')
        closure = sources()
        save(HERE / 'build-receipt.json', dict(passed=True, device_executed=False,
             build='Python compile() in memory; no native build or bytecode cache', sources=closure))
        cmd = [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(HERE), '-p', 'test_*.py', '-v']
        with (HERE / 'cpu-tests.log').open('w') as log:
            result = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)
        require(result.returncode == 0, 'CPU fixture/checks failed; see cpu-tests.log')
        expected, actual = HERE / 'fixture-expected.bin', HERE / 'fixture-actual.bin'
        require(expected.stat().st_size > 0 and expected.read_bytes() == actual.read_bytes(), 'request bytes changed')
        save(HERE / 'byte-fixture.json', dict(passed=True, device_executed=False,
            changed_class='screen request orchestration', command=cmd,
            scope='v1/v2 complete fake-transport request/reset flow, byte-identical 12 request receipts',
            build_receipt_sha256=sha(HERE / 'build-receipt.json'), bytes=expected.stat().st_size,
            expected_sha256=sha(expected), actual_sha256=sha(actual), native_execution=False))
        require(closure == sources(), 'sources changed during CPU gate')
        artifacts = {name:sha(HERE / name) for name in
                     ('build-receipt.json','cpu-tests.log','byte-fixture.json','fixture-expected.bin','fixture-actual.bin')}
        save(HERE / 'wrapper-seal.json', dict(schema='own-runtime.screen.wrapper-seal.v2',
            passed=True, device_executed=False, sources=closure, artifacts=artifacts,
            device_exactness='pending coordinator screen: 12 x 128 against packet49', speed='unmeasured'))
        verify()
    print('screen v2 CPU seal verified; device execution: false')


if __name__ == '__main__':main()
