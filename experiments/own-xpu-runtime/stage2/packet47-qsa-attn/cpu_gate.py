#!/usr/bin/env python3
"""Build and execute only native CPU code; accelerator runtimes are rejected."""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ALLOWED_CPUS = set(range(4, 16)) | set(range(20, 32))
FLAGS = ['-std=c++20', '-O2', '-fno-fast-math', '-ffp-contract=off', '-fno-associative-math']


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def require_cpu_limits():
    if os.getpriority(os.PRIO_PROCESS, 0) != 19 or not os.sched_getaffinity(0) <= ALLOWED_CPUS:
        raise ValueError('requires nice -n 19 taskset -c 4-15,20-31')
    if not os.sched_getaffinity(0):
        raise ValueError('empty CPU affinity')
    if shutil.disk_usage(HERE).free < 8_100_000_000:
        raise ValueError('preserve 8 GB disk reserve plus 100 MB build allowance')


def sources():
    names = [HERE / n for n in ('cpu_gate.py', 'cpu_test.cpp', 'qsa_reference.hpp')]
    names += [HERE.parent / 'packet45-merged3' / n for n in ('kernels.hpp', 'detmath.hpp', 'rope.hpp')]
    names.append(HERE.parent / 'packet17-detmath/detmath.hpp')
    return {str(p.relative_to(ROOT)): sha(p) for p in names}


def verify(mapping, base):
    for name, digest in mapping.items():
        if sha(base / name) != digest:
            raise ValueError('source/artifact changed: ' + name)


def build():
    require_cpu_limits()
    before = sources()
    output = HERE / 'build/host'
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, compiler in [('gnu', '/usr/bin/g++'), ('intel', '/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
        binary = output / ('cpu-test-' + name)
        command = [compiler, *FLAGS, str(HERE / 'cpu_test.cpp'), '-o', str(binary)]
        log = output / ('build-' + name + '.log')
        with log.open('w') as f:
            subprocess.run(command, check=True, stdout=f, stderr=subprocess.STDOUT)
        dynamic = subprocess.run(['readelf', '-d', str(binary)], check=True, text=True, capture_output=True).stdout
        if any(n in dynamic.lower() for n in ('libsycl', 'libze_loader', 'libur_loader', 'libopencl')):
            raise ValueError('host test linked accelerator runtime')
        version = subprocess.run([compiler, '--version'], check=True, text=True, capture_output=True).stdout
        rows.append(dict(name=name, command=command, compiler_version=version,
                         binary=str(binary.relative_to(HERE)), binary_sha256=sha(binary),
                         build_log_sha256=sha(log), dynamic_dependencies=dynamic))
    verify(before, ROOT)
    receipt = dict(schema='ownrt.packet47.cpu-build.v1', passed=True, device_executed=False,
                   source_hashes=before, artifacts={r['binary']: r['binary_sha256'] for r in rows},
                   compilers=rows, completed_utc=datetime.now(timezone.utc).isoformat())
    (HERE / 'build-host.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(dict(passed=True, device_executed=False, compilers=len(rows))), flush=True)


def gate():
    require_cpu_limits()
    build_path = HERE / 'build-host.json'
    build_receipt = json.loads(build_path.read_text())
    if build_receipt.get('passed') is not True or build_receipt.get('device_executed') is not False:
        raise ValueError('passing host-only build required')
    verify(build_receipt['source_hashes'], ROOT)
    verify(build_receipt['artifacts'], HERE)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    output = HERE / 'evidence' / ('cpu-' + stamp)
    output.mkdir(parents=True, exist_ok=False)
    repeats = []
    for compiler in build_receipt['compilers']:
        for repeat in (1, 2):
            label = compiler['name'] + '-' + str(repeat)
            raw, log, errors = (output / (label + suffix) for suffix in ('.raw', '.jsonl', '.stderr'))
            command = [str(HERE / compiler['binary']), str(raw)]
            started = datetime.now(timezone.utc).isoformat()
            with log.open('w') as stdout, errors.open('w') as stderr:
                subprocess.run(command, check=True, stdout=stdout, stderr=stderr, timeout=1800)
            rows = [json.loads(line) for line in log.read_text().splitlines()]
            summary, cases = rows[-1], rows[:-1]
            if summary.get('passed') is not True or summary.get('device_executed') is not False:
                raise ValueError('CPU test failed')
            if len(cases) != summary['cases'] or any(r.get('passed') is not True for r in cases):
                raise ValueError('incomplete CPU matrix')
            required = {(c, m, seed) for c in (1024, 2048, 4096, 8192, 32768) for m in (1, 2) for seed in (47, 4701)}
            if not required <= {(r['context'], r['rows'], r['seed']) for r in cases}:
                raise ValueError('requested context/input matrix incomplete')
            compressed = raw.with_suffix('.raw.gz')
            raw_hash, raw_bytes = sha(raw), raw.stat().st_size
            # Retain every compared output byte, compressed losslessly. No
            # binary is accepted by a hash alone: C++ first compares raw bytes.
            compressed.write_bytes(gzip.compress(raw.read_bytes(), mtime=0))
            if hashlib.sha256(gzip.decompress(compressed.read_bytes())).hexdigest() != raw_hash:
                raise ValueError('raw evidence retention mismatch')
            raw.unlink()
            repeats.append(dict(compiler=compiler['name'], repeat=repeat, command=command,
                                started_utc=started, summary=summary, raw_sha256=raw_hash,
                                raw_bytes=raw_bytes, case_rows=cases,
                                files={str(p.relative_to(HERE)): sha(p) for p in (log, errors, compressed)}))
            print(label, json.dumps(summary), flush=True)
    if len({r['summary']['pid'] for r in repeats}) != len(repeats):
        raise ValueError('fresh process identity repeated')
    if len({r['raw_sha256'] for r in repeats}) != 1:
        raise ValueError('fresh process/compiler raw outputs differ')
    if any(r['case_rows'] != repeats[0]['case_rows'] for r in repeats[1:]):
        raise ValueError('fresh compiler diagnostic rows differ')
    verify(build_receipt['source_hashes'], ROOT)
    verify(build_receipt['artifacts'], HERE)
    receipt = dict(schema='ownrt.packet47.cpu-gates.v1', passed=True, device_executed=False,
                   fresh_process_repeats_equal=True, cross_compiler_outputs_equal=True,
                   build_receipt_sha256=sha(build_path), source_hashes=build_receipt['source_hashes'],
                   artifacts=build_receipt['artifacts'], repeats=repeats,
                   evidence={n: h for r in repeats for n, h in r['files'].items()},
                   device_exactness='pending E1/E2', logits_measured=False,
                   completed_utc=datetime.now(timezone.utc).isoformat())
    (HERE / 'cpu-gates.json').write_text(json.dumps(receipt, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('build', 'test'))
    args = parser.parse_args()
    (build if args.mode == 'build' else gate)()
