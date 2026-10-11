"""Build only CPU binaries in a new scratch directory; retain source identities."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
P13 = HERE.parent
ROOT = P13.parents[3]
OWNER = ROOT / 'experiments/own-xpu-runtime/stage1/packet3-prep/src'


def build(scratch, receipt):
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert os.environ['OMP_NUM_THREADS'] == '2'
    scratch = Path(scratch).resolve()
    scratch.mkdir(exist_ok=False)
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    source = (P13 / 'performance.cpp').read_text()
    needle = '        for(size_t row=0;row<m.rows;++row) {'
    assert source.count(needle) == 1
    replacement = '        #pragma omp parallel for schedule(static) num_threads(8)\n' + needle
    parallel = scratch / 'performance-cpu.cpp'
    parallel.write_text(source.replace(needle, replacement))
    common = ['g++', '-std=c++20', '-O2', '-fno-fast-math', '-ffp-contract=off', '-DOWN_RT_HOST_ONLY']
    includes = ['-I'+str(p) for p in [OWNER, P13, P13.parent/'packet2/kernels', P13.parent/'packet2/loader']]
    dependencies = [P13.parent/'packet4/kernels.cpp', P13.parent/'packet4/owner_retire.cpp',
                    P13.parent/'packet2/loader/gguf.cpp', OWNER/'owner.cpp']
    commands = []
    for name, main, performance, extra in [
        ('original-host', P13/'main.cpp', P13/'performance.cpp', []),
        ('host-check', HERE/'host_check.cpp', parallel, ['-fopenmp']),
    ]:
        cmd = list(map(str, common+extra+includes+[main, performance, *dependencies, '-lcrypto', '-o', scratch/name]))
        subprocess.run(cmd, check=True)
        dynamic = subprocess.check_output(['readelf', '-d', str(scratch/name)], text=True)
        assert not any(x in dynamic.lower() for x in ['libsycl', 'ze_loader', 'libur_loader', 'opencl', 'libcuda'])
        commands.append(dict(argv=cmd, binary_sha256=sha(scratch/name), dynamic_dependencies=dynamic))
    files = [P13/'main.cpp', P13/'performance.cpp', HERE/'host_check.cpp', Path(__file__), *dependencies]
    for folder in [OWNER, *(P13.parent/n for n in ['packet2', 'packet3', 'packet4', 'packet6-kopt', 'packet7-kopt2', 'packet8-kopt3', 'packet9-kopt4', 'packet13-integrate'])]:
        files.extend(p for p in folder.rglob('*.hpp') if 'build' not in p.relative_to(folder).parts)
    Path(receipt).write_text(json.dumps(dict(device_executed=False, commands=commands,
        source_sha256={str(p.relative_to(ROOT)):sha(p) for p in sorted(set(files))},
        row_parallel_overlay=dict(search=needle, replacement=replacement, generated_sha256=sha(parallel))), indent=2)+'\n')


if __name__ == '__main__':
    build(*sys.argv[1:])
