#!/usr/bin/env python3
"""CPU-only build/gate/throughput receipt. Refuses before the protected cutoff."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from preparation import exclusive_cpu_work

BUILD = HERE / 'build'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, path, *, timeout=180):
    started = datetime.now(timezone.utc).isoformat()
    process = subprocess.run(command, cwd=HERE, text=True, capture_output=True,
                             timeout=timeout, check=False)
    path.with_suffix('.stdout').write_text(process.stdout)
    path.with_suffix('.stderr').write_text(process.stderr)
    record = dict(command=list(map(str, command)), started_utc=started,
                  finished_utc=datetime.now(timezone.utc).isoformat(),
                  returncode=process.returncode)
    path.with_suffix('.command.json').write_text(json.dumps(record, indent=2) + '\n')
    if process.returncode:
        raise RuntimeError(f'{path.name} failed: {process.stderr[-1500:]}')
    return process.stdout


def source_pins():
    # GCC depfile records actual transitive local headers; external system headers
    # are compiler/runtime identity, not copied into this packet.
    text = (BUILD / 'cpu-expert.d').read_text().replace('\\\n', ' ')
    dependencies = text.split(':', 1)[1].split()
    result = {}
    for name in dependencies:
        path = (HERE / name).resolve()
        result[os.path.relpath(path, HERE)] = sha(path)
    result['run.py'] = sha(Path(__file__))
    result['../preparation.py'] = sha(HERE.parent / 'preparation.py')
    return dict(sorted(result.items()))


def verify_build():
    identity = json.loads((BUILD / 'identity.json').read_text())
    if identity['binary_sha256'] != sha(BUILD / 'cpu-expert'):
        raise RuntimeError('CPU binary changed since build')
    for relative, expected in identity['sources'].items():
        if sha((HERE / relative).resolve()) != expected:
            raise RuntimeError(f'CPU source changed since build: {relative}')
    return identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('build', 'test', 'bench'))
    parser.add_argument('--output', type=Path, required=True,
                        help='new receipt directory; never overwritten')
    parser.add_argument('--seconds', type=float, default=2)
    parser.add_argument('--samples', type=int, default=5)
    parser.add_argument('--threads', type=int, default=24)
    args = parser.parse_args()
    if not (1 <= args.seconds <= 10 and 3 <= args.samples <= 15 and 1 <= args.threads <= 24):
        parser.error('bounded benchmark: seconds 1..10, samples 3..15, threads 1..24')
    if args.output.exists():
        parser.error('receipt directory must be new')
    with exclusive_cpu_work(planned_write_bytes=25_000_000) as limits:
        cpuinfo = Path('/proc/cpuinfo').read_text()
        flags = set(re.search(r'^flags\s*:\s*(.*)$', cpuinfo, re.M).group(1).split())
        if not {'avx2', 'fma'} <= flags:
            raise RuntimeError('this implementation requires AVX2 and explicit FMA for deterministic math')
        args.output.mkdir(parents=True)
        BUILD.mkdir(exist_ok=True)
        report = dict(schema='p46.cpu-expert.receipt.v1', action=args.action,
                      limits=limits, cpu_model=re.search(r'^model name\s*:\s*(.*)$', cpuinfo, re.M).group(1),
                      avx2=True, avx512='avx512f' in flags, host=platform.node(),
                      device_ran=False, device_executed=False, model_weights_read=False)
        if args.action == 'build':
            common = ['g++', '-std=c++20', '-O3', '-mavx2', '-mfma',
                      '-fno-fast-math', '-ffp-contract=off', '-frounding-math',
                      '-fopenmp', '-Wall', '-Wextra', '-Wno-unknown-pragmas']
            run(common + ['-MM', '-MF', str(BUILD / 'cpu-expert.d'), 'main.cpp'],
                args.output / 'dependencies')
            before = source_pins()
            before_time = datetime.now(timezone.utc).isoformat()
            command = common + ['-MMD', '-MF', str(BUILD / 'cpu-expert.d'),
                                'main.cpp', '-o', str(BUILD / 'cpu-expert')]
            run(command, args.output / 'compile')
            after = source_pins()
            if before != after:
                raise RuntimeError('CPU source closure changed during compilation; binary refused')
            identity = dict(command=command, binary_sha256=sha(BUILD / 'cpu-expert'),
                            sources=after, sources_pinned_before_compile_utc=before_time,
                            source_closure_unchanged_during_compile=True,
                            compiler=subprocess.check_output(['g++', '--version'], text=True).splitlines()[0])
            (BUILD / 'identity.json').write_text(json.dumps(identity, indent=2) + '\n')
            report['build'] = identity
        elif args.action == 'test':
            report['build'] = verify_build()
            results = [json.loads(run([str(BUILD / 'cpu-expert'), 'test'], args.output / f'test-{i}')) for i in range(2)]
            if results[0] != results[1] or not all(result['passed'] for result in results):
                raise RuntimeError('fresh-process CPU gates differ or failed')
            report.update(results=results, fresh_process_repeats_equal=True,
                          nonfinite_oracle_qualified=False)
            (BUILD / 'exactness.json').write_text(json.dumps(report, indent=2) + '\n')
        else:
            report['build'] = verify_build()
            exactness = json.loads((BUILD / 'exactness.json').read_text())
            if exactness['build'] != report['build'] or not exactness['fresh_process_repeats_equal']:
                raise RuntimeError('benchmark requires matching fresh-process exactness gate')
            report['exactness_receipt_sha256'] = sha(BUILD / 'exactness.json')
            report['openmp_environment'] = {key: value for key, value in os.environ.items()
                                            if key.startswith(('OMP_', 'GOMP_'))}
            results = [json.loads(run([str(BUILD / 'cpu-expert'), 'bench', str(args.seconds),
                                      str(args.samples), str(args.threads)], args.output / f'bench-{i}',
                                     timeout=300)) for i in range(2)]
            report.update(results=results, repeat_processes=2,
                          throughput_is_model_speed=False, dram_bandwidth_measured=False)
        if verify_build() != report['build']:
            raise RuntimeError('CPU build identity changed during action; receipt refused')
        report['finished_utc'] = datetime.now(timezone.utc).isoformat()
        report['passed'] = True
        (args.output / 'receipt.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(dict(receipt=str(args.output / 'receipt.json'), passed=True)))


if __name__ == '__main__':
    main()
