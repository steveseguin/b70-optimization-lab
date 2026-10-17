#!/usr/bin/env python3
"""Serial CPU compilation only; never execute the device engine."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
B = P / 'build'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')

def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8,16)) | set(range(24,32))
    assert os.environ.get('OMP_NUM_THREADS') == '2'
    B.mkdir(exist_ok=True)
    (B / 'tmp').mkdir(exist_ok=True)
    os.environ['TMPDIR'] = str(B / 'tmp')
    commands = []
    def run(command, name):
        command = list(map(str, command))
        commands.append(command)
        with (B / (name + '.log')).open('w') as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
        print(name, 'PASS', flush=True)
    compiler = '/opt/intel/oneapi/compiler/2026.0/bin/icpx'
    run(['cmake', '-S', P, '-B', B/'device', '-DCMAKE_CXX_COMPILER='+compiler,
         '-DOWN_RT_HOST_ONLY=OFF'], 'configure')
    run(['cmake', '--build', B/'device', '--target', 'own-rt-iq3', '-j1'], 'device-build')
    for stem in ('native_controller_test', 'native_mailbox_fault_test'):
        run(['g++', '-std=c++20', '-O2', '-fno-fast-math', '-ffp-contract=off',
             '-pthread', P/(stem+'.cpp'), '-o', B/stem], stem+'-build')
    parent = P.parent/'packet56-draft-prefix'
    run(['g++', '-std=c++20', '-O2', '-fno-fast-math', '-ffp-contract=off',
         '-pthread', parent/'native_controller_test.cpp', '-o', B/'parent-controller'], 'parent-controller-build')
    (P/'evidence').mkdir(exist_ok=True)
    save(P/'evidence/compile.json', dict(passed=True, device_executed=False,
         commands=commands, cpu_affinity=sorted(os.sched_getaffinity(0)), nice=19,
         compiler_version=subprocess.check_output([compiler,'--version'],text=True),
         compile_commands_sha256=sha(B/'device/compile_commands.json'),
         link_sha256=sha(B/'device/CMakeFiles/own-rt-iq3.dir/link.txt')))
    from math_gate import closure
    paths = set(closure()) | {P/n for n in ('CMakeLists.txt','build_spin.py','host_spin.hpp',
        'kernel_gate.py','kernel_overlay.py','submission_overlay.py','math_gate.py',
        'kernel_guard.hpp','rope.bf16','native_controller_test.cpp','native_mailbox_fault_test.cpp',
        'parent-source-manifest.json','mtp-manifest.tsv','evidence/compile.json')}
    paths |= {parent/'native_controller_test.cpp', parent/'native_controller.hpp'}
    save(P/'build-device-receipt.json', dict(passed=True, device_executed=False,
         schema='packet56w.lean-build.v1',
         sources={str(x.relative_to(ROOT)):sha(x) for x in sorted(paths)},
         artifacts={str(x.relative_to(P)):sha(x) for x in
             [B/'device/own-rt-iq3',B/'native_controller_test',B/'native_mailbox_fault_test',B/'parent-controller']}))

if __name__ == '__main__':
    main()
