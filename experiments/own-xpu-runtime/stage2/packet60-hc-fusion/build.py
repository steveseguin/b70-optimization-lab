#!/usr/bin/env python3
"""Build packet60 primitives and run the one CPU byte fixture; never use a GPU."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
PARENT = P.parent / 'packet56-draft-prefix'
B = P / 'build'
MIRROR = PARENT / 'build/checked' / PARENT.relative_to(ROOT)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    assert not (P / 'primitive-seal.json').exists(), 'sealed packet: do not rebuild'
    B.mkdir(exist_ok=True)
    (B / 'tmp').mkdir(exist_ok=True)
    os.environ['TMPDIR'] = str(B / 'tmp')
    commands = []

    def run(command, name):
        commands.append(dict(command=list(map(str, command)), cwd=str(ROOT), name=name))
        with (B / (name + '.log')).open('w') as log:
            subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)

    for name in ('p60_math.hpp', 'p60_kernels.hpp', 'fixture.cpp'):
        def include(match):
            target = (B if match[1].startswith('p60_') else PARENT if match[1] == 'kernel_guard.hpp' else MIRROR) / match[1]
            return '#include ' + json.dumps(str(target))
        (B / name).write_text(re.sub(r'#include "([^\"]+)"', include, (P / name).read_text()))
    # External functions force all three submission bodies into the native
    # object. The object is compiled, never loaded or executed during this gate.
    (B / 'device-primitives.cpp').write_text(
        '#include "p60_kernels.hpp"\n'
        'sycl::event p60_compile_norm(sycl::queue&q,p60::Bound b,const std::vector<sycl::event>&d){return p60::norm_kernel(q,b,d);}\n'
        'sycl::event p60_compile_low(sycl::queue&q,p60::Bound b,const std::vector<sycl::event>&d){return p60::low_inject_kernel(q,b,d);}\n'
        'sycl::event p60_compile_gate(sycl::queue&q,p60::Bound b,const std::vector<sycl::event>&d){return p60::gate_mix_kernel(q,b,d);}\n')
    flags = ['-std=c++20', '-O2', '-fno-fast-math', '-ffp-contract=off']
    run(['/usr/bin/g++', *flags, '-fopenmp', str(B / 'fixture.cpp'), '-o', str(B / 'fixture')], 'compile-cpu')
    run(['/opt/intel/oneapi/compiler/2026.0/bin/icpx', *flags, '-fsycl', '-fdenormal-fp-math=ieee',
         '-foffload-fp32-prec-div', '-foffload-fp32-prec-sqrt', '-c', str(B / 'device-primitives.cpp'),
         '-o', str(B / 'device-primitives.o')], 'compile-device')
    # Compiler dependency scans bind actual checked headers, not just their
    # original source names or a hand-maintained include allow-list.
    run(['/opt/intel/oneapi/compiler/2026.0/bin/icpx', *flags, '-fsycl', '-MM',
         str(B / 'device-primitives.cpp')], 'dependencies')
    raw = (B / 'dependencies.log').read_text().replace('\\\n', ' ')
    # icpx emits both host and device make rules inside offload-bundle markers.
    paths = {Path(x) for x in re.findall(r'/[^\s\\]+', raw)}
    assert paths and all(x.is_file() for x in paths)
    paths.update(P.glob('*.py'))
    paths.update(P.glob('*.hpp'))
    paths.add(P / 'fixture.cpp')
    paths.add(PARENT / 'build-receipt.json')
    sources = {str(x.relative_to(ROOT)): sha(x) for x in sorted(paths)}
    save(P / 'commands.json', commands)
    sources[str((P / 'commands.json').relative_to(ROOT))] = sha(P / 'commands.json')
    receipt = dict(schema='packet60.primitive-build.v1', passed=True, device_executed=False,
                   engine_integrated=False, sources=sources,
                   artifacts={str(x.relative_to(P)): sha(x) for x in (B / 'fixture', B / 'device-primitives.o')})
    save(P / 'build-device-receipt.json', receipt)
    command = [str(B / 'fixture'), str(P / 'fixture')]
    run(command, 'cpu-byte-fixture')
    result = json.loads((B / 'cpu-byte-fixture.log').read_text())
    expected, actual = P / 'fixture/expected.bin', P / 'fixture/actual.bin'
    assert expected.read_bytes() == actual.read_bytes()
    result.update(schema='own-runtime.screen.byte-fixture.v1', changed_class='HC arithmetic primitives; engine integration pending',
                  command=command, build_receipt_sha256=sha(P / 'build-device-receipt.json'), sources=sources,
                  expected=dict(path=str(expected.relative_to(P)), sha256=sha(expected)),
                  actual=dict(path=str(actual.relative_to(P)), sha256=sha(actual)))
    save(P / 'fixture/receipt.json', result)
    print(json.dumps({k: result[k] for k in ('passed', 'device_executed', 'cases', 'bytes_compared')}))


if __name__ == '__main__':
    main()
