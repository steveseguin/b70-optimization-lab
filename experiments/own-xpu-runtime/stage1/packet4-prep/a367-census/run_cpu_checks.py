#!/usr/bin/env python3
"""Lean CPU build checks. No model weights, runtime import, native action or approval."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
OUT = REPO / 'data/2026-10-17-flash-next-a367-census-reseal'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert os.sched_getaffinity(0) == set(range(4,16)) | set(range(20,32))
    OUT.mkdir(exist_ok=True)
    suites = [
        ('census', HERE, 'test_*.py', '/usr/bin/python3'),
        ('replay', HERE.parent / 'a367-replay', 'test_replay.py', '/usr/bin/python3'),
        ('calibration', HERE.parent / 'a367-calibrate', 'test_calibrate.py', '/usr/bin/python3'),
        ('driver', HERE.parent / 'driver', 'test_driver.py', '/home/steve/.venvs/vllm-xpu/bin/python3'),
        ('payload', REPO / 'scripts', 'test_verify_flash_next_a367_launch_payload.py', '/usr/bin/python3'),
        ('tree', REPO / 'scripts', 'test_verify_qwen38_flash_next_fp8_tree.py', '/usr/bin/python3'),
        ('feasibility', HERE / 'feasibility', 'test_cpu.py', '/usr/bin/python3'),
    ]
    result = {'schema': 'a367-census-cpu-build-v1', 'native_executed': False, 'owner_approval_recorded': False,
              'nice': 19, 'test_environment': {'OMP_NUM_THREADS': '2'}, 'affinity': sorted(os.sched_getaffinity(0)), 'suites': [], 'seals': [], 'plans': []}
    for name, directory, pattern, python in suites:
        cmd = [python, '-B', '-m', 'unittest', 'discover', '-s', str(directory), '-p', pattern, '-v']
        run = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, env={**os.environ, 'OMP_NUM_THREADS': '2'})
        output = run.stdout + run.stderr
        log = OUT / (name + '.log'); log.write_text(output)
        match = re.search(r'Ran (\d+) tests?', output)
        count = int(match[1]) if match else 0
        passed = run.returncode == 0 and count > 0 and re.search(r'^OK\s*$', output, re.M) is not None
        result['suites'].append(dict(suite=name, command=cmd, tests=count, returncode=run.returncode,
            passed=passed, log=log.name, log_sha256=sha(log)))
        print(f'{name}: {count} tests; passed={passed}', flush=True)
    for seal in (HERE/'seal.json', HERE.parent/'a367-replay/seal.json',
                 HERE.parent/'a367-calibrate/seal.json', HERE.parent/'driver/driver-seal.json'):
        files = json.loads(seal.read_text())['files']
        base = seal.parent if seal.name == 'driver-seal.json' else REPO
        mismatches = [p for p,d in files.items() if not (base/p).is_file() or sha(base/p) != d]
        result['seals'].append(dict(path=str(seal.relative_to(REPO)), sha256=sha(seal), files=len(files), mismatches=mismatches))
    for arm in ('graph-reference', 'graph-census', 'eager-census'):
        cmd = ['/usr/bin/python3', '-B', str(HERE/'a367_census.py'), '--plan', '--arm', arm,
               '--output', '/mnt/raid-models/bench-results/a367c-20261017T000000Z']
        run = subprocess.run(cmd, capture_output=True, text=True, check=True)
        path = OUT / (arm + '-plan.json'); path.write_text(run.stdout)
        plan = json.loads(run.stdout)
        assert plan['native_executed'] is False
        result['plans'].append(dict(arm=arm, path=path.name, sha256=sha(path)))
    for path in HERE.glob('*.sh'):
        subprocess.run(['bash', '-n', str(path)], check=True)
    for path in HERE.glob('*.py'):
        ast.parse(path.read_text(), filename=str(path))
    result['tests'] = sum(s['tests'] for s in result['suites'])
    result['seal_mismatches'] = sum(len(s['mismatches']) for s in result['seals'])
    result['preregistration_sha256'] = sha(HERE/'preregistration.json')
    result['passed'] = all(s['passed'] for s in result['suites']) and result['seal_mismatches'] == 0
    result['syntax_checks'] = True
    result['unitrace_smoke'] = 'Not run: even ITT-only tracer initialization calls zeInit(GPU_ONLY) in pinned source; static hashes only. No device access authorized.'
    (OUT/'cpu-tests.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'tests': result['tests'], 'passed': result['passed'], 'seal_mismatches': result['seal_mismatches']}))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
