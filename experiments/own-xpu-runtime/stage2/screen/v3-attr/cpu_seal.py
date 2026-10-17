#!/usr/bin/env python3
"""Build Python in memory, run the small CPU fixture/checks, seal; never a device."""
import argparse
import os
import subprocess
import sys
from pathlib import Path
from common import HERE, ROOT, P56, P58, D, S, SUPPORT, W, M, DISPATCH, read, require, save, sha
from conditions import cpu_gate
import fault_review

ARTIFACTS = HERE / 'placement-validation'


def sources():
    paths = set(HERE.glob('*.py'))
    paths.update(HERE / name for name in ('reference.json','integration.patch','screen-integration.patch'))
    paths.add(HERE / 'placements.json')
    paths.add(HERE / 'placement-jobs.txt')
    paths.add(P56 / 'memory-plan.json')
    paths.update(P56 / name for name in ('pipeline.py', 'suite.py', 'storage.py', 'suite_metrics.py', 'memory_gate.py'))
    paths.add(HERE.parent / 'tp2_worker.py')  # unchanged reference used by the fixture
    paths.add(P58 / 'oracle-binding.json')
    paths.update(HERE.parent.parent / 'packet64-attribution' / name
                 for name in ('summarize.py', 'timeline.py'))
    paths.add(fault_review.DRIVER)
    paths.update(Path(module.__file__) for module in (D, D.CHECK, D.METRICS, S, SUPPORT, W, M, DISPATCH))
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}


def verify():
    row = read(ARTIFACTS / 'wrapper-seal.json')
    require(row.get('passed') is True and row.get('device_executed') is False,
            'wrapper CPU seal missing or failed')
    require(row['sources'] == sources(), 'screen v3 source closure changed; CPU reseal required')
    for name, digest in row['artifacts'].items():
        require(sha(ARTIFACTS / name) == digest, 'wrapper artifact changed: ' + name)
    require(sha(ARTIFACTS / 'fixture-actual.bin') == sha(ARTIFACTS / 'fixture-expected.bin'), 'wrapper byte fixture differs')
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--verify', action='store_true')
    args = ap.parse_args()
    cpu_gate()
    if args.verify:
        verify()
    else:
        require(not (ARTIFACTS / 'wrapper-seal.json').exists(), 'never overwrite wrapper seal')
        ARTIFACTS.mkdir(exist_ok=True)
        for path in HERE.glob('*.py'):
            compile(path.read_text(), str(path), 'exec')
        closure = sources()
        save(ARTIFACTS / 'build-receipt.json', dict(passed=True, device_executed=False,
             build='Python compile() in memory; no native build or bytecode cache', sources=closure,
             cpu_conditions=dict(nice=os.getpriority(os.PRIO_PROCESS, 0),
                                 affinity=sorted(os.sched_getaffinity(0))),
             storage_admission=SUPPORT.storage(HERE, 1024**2)))
        cmd = [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(HERE), '-p', 'test_*.py', '-v']
        with (ARTIFACTS / 'cpu-tests.log').open('w') as log:
            result = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)
        require(result.returncode == 0, 'CPU fixture/checks failed; see cpu-tests.log')
        expected, actual = ARTIFACTS / 'fixture-expected.bin', ARTIFACTS / 'fixture-actual.bin'
        require(expected.stat().st_size > 0 and expected.read_bytes() == actual.read_bytes(), 'request bytes changed')
        save(ARTIFACTS / 'byte-fixture.json', dict(passed=True, device_executed=False,
            changed_class='screen request orchestration', command=cmd,
            scope='v1/v3 complete fake-transport request/reset flow, byte-identical 12 request receipts',
            build_receipt_sha256=sha(ARTIFACTS / 'build-receipt.json'), bytes=expected.stat().st_size,
            expected_sha256=sha(expected), actual_sha256=sha(actual), native_execution=False))
        require(closure == sources(), 'sources changed during CPU gate')
        artifacts = {name:sha(ARTIFACTS / name) for name in
                     ('build-receipt.json','cpu-tests.log','byte-fixture.json','fixture-expected.bin','fixture-actual.bin')}
        save(ARTIFACTS / 'wrapper-seal.json', dict(schema='own-runtime.screen.wrapper-seal.v3-placement1',
            passed=True, device_executed=False, sources=closure, artifacts=artifacts,
            predecessor_wrapper_sha256=sha(HERE / 'wrapper-seal.json'),
            device_exactness='pending coordinator screen: 12 x 128 against packet49', speed='unmeasured'))
        verify()
    print('screen v3 CPU seal verified; device execution: false')


if __name__ == '__main__':main()
