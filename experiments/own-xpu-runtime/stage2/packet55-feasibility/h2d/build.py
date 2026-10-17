#!/usr/bin/env python3
"""Serial CPU-only SYCL compilation. Does not enumerate or launch a GPU."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
COMPILER = Path('/opt/intel/oneapi/compiler/2026.0/bin/icpx')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19, 'nice 19 required'
    assert set(os.sched_getaffinity(0)) <= set(range(4, 16)) | set(range(20, 32)), 'restricted affinity required'
    build = HERE / 'build'
    build.mkdir(exist_ok=True)
    binary = build / 'stream-bench'
    command = [str(COMPILER), '-std=c++20', '-O2', '-fsycl', '-ffp-contract=off',
               str(HERE / 'stream_bench.cpp'), '-lze_loader', '-o', str(binary)]
    with (build / 'compile.log').open('w') as out:
        result = subprocess.run(command, stdout=out, stderr=subprocess.STDOUT)
    assert result.returncode == 0, 'see build/compile.log'
    row = {'schema': 'ownrt.packet55.h2d.build.v1', 'passed': True, 'device_executed': False,
           'command': command, 'compiler_sha256': sha(COMPILER), 'binary_sha256': sha(binary),
           'source_sha256': sha(HERE / 'stream_bench.cpp'), 'binary_bytes': binary.stat().st_size,
           'nice': 19, 'affinity': sorted(os.sched_getaffinity(0))}
    (HERE / 'build-receipt.json').write_text(json.dumps(row, indent=2) + '\n')
    print(json.dumps(row))

if __name__ == '__main__':
    main()
