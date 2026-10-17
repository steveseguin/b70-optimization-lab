"""Offline BMG code for the failed head; compilation only, no device execution."""
import json
import os
import resource
import subprocess
from pathlib import Path
from build_engine import P, ROOT, limits, save, sha


def main():
    limits()
    resource.setrlimit(resource.RLIMIT_AS, (8*1024**3, 8*1024**3))
    out = P / 'build/head-inspection-r3'
    out.mkdir(exist_ok=False)
    compiler = Path('/opt/intel/oneapi/compiler/2026.0/bin/icpx')
    source = P / 'build/checked' / P.relative_to(ROOT) / 'p69_head.cpp'
    commands = [
        [str(compiler), '-fsycl', '-fsycl-device-only', '-O2', '-std=c++20',
         '-fno-fast-math', '-ffp-contract=off', '-fdenormal-fp-math=ieee',
         '-foffload-fp32-prec-div', '-foffload-fp32-prec-sqrt',
         '-c', str(source), '-o', str(out / 'head.bc')],
        [str(compiler.parent / 'compiler/llvm-spirv'),
         '--spirv-ext=+all,-SPV_INTEL_runtime_aligned,-SPV_KHR_untyped_pointers',
         str(out / 'head.bc'), '-o', str(out / 'head.spv')],
        ['/usr/bin/ocloc', 'compile', '-spirv_input', '-file', str(out / 'head.spv'),
         '-device', 'bmg-g31', '-out_dir', str(out / 'aot')]]
    env = {**os.environ, 'OMP_NUM_THREADS': '1', 'OMP_THREAD_LIMIT': '1',
           'IGC_ShaderDumpEnable': '1', 'IGC_DumpToCustomDir': str(out / 'igc'),
           'IGC_ShowFullVectorsInShaderDumps': '1'}
    for i, cmd in enumerate(commands):
        with (out / f'compile-{i}.log').open('w') as log:
            subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=log,
                           stderr=subprocess.STDOUT, env=env, check=True, timeout=300)
        print('offline head stage', i, 'PASS', flush=True)
    save(out / 'receipt.json', dict(device_executed=False, commands=commands,
                                   source_sha256=sha(source)))


if __name__ == '__main__':
    main()
