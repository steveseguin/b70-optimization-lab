#!/usr/bin/env python3
"""CPU builds/tests only; native objects are compiled, never linked or run."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BUILD = HERE/'build'
PYTHON = '/home/steve/.venvs/vllm-xpu/bin/python'
if os.getpriority(os.PRIO_PROCESS, 0) != 19 or os.environ.get('OMP_NUM_THREADS') != '2':
    raise SystemExit('Run at nice 19 with OMP_NUM_THREADS=2')
if BUILD.is_symlink():
    raise SystemExit('Refuse symlink build directory')
receipt = {'schema': 'own-xpu-runtime.packet3-prep.build.v1',
           'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
           'host': platform.node(), 'cwd': str(ROOT), 'nice': 19, 'OMP_NUM_THREADS': '2',
           'native_executed': False, 'native_executable_linked': False,
           'commands': [], 'passed': False,
           'development_failure': 'Initial SYCL configure: dpkg format ${Version} expanded to empty by CMake. Fixed with bracket quoting; no GPU execution.',
           'toolchain_inventory_sha256': hashlib.sha256((HERE/'../../data/toolchain-20261010.json').read_bytes()).hexdigest()}

def run(args):
    command = ['nice', '-n', '19', 'env', 'OMP_NUM_THREADS=2', *map(str,args)]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    receipt['commands'].append({'argv': command, 'returncode': result.returncode,
                                'stdout': result.stdout, 'stderr': result.stderr})
    print(result.stdout, end='', flush=True)
    if result.stderr:
        print(result.stderr, end='', flush=True)
    if result.returncode:
        raise RuntimeError(f'command failed: {args}')
    return result.stdout

try:
    for command in [ ['/opt/intel/oneapi/compiler/2026.0/bin/icpx', '--version'],
                    ['cmake','--version'], ['dpkg-query','-W','libze-dev','libze1'] ]:
        run(command)
    for mode, flag in [('host', 'ON'), ('sycl', 'OFF')]:
        run(['cmake','-S',HERE,'-B',BUILD/mode,f'-DOWN_RT_HOST_ONLY={flag}',
             '-DOWN_RT_BUILD_NATIVE_SMOKE=OFF',f'-DPython3_EXECUTABLE={PYTHON}'] if mode=='host'
            else ['cmake','-S',HERE,'-B',BUILD/mode,f'-DOWN_RT_HOST_ONLY={flag}','-DOWN_RT_BUILD_NATIVE_SMOKE=OFF'])
        run(['cmake','--build',BUILD/mode,'--clean-first','--verbose','-j2'])
    receipt['test_output'] = run(['ctest','--test-dir',BUILD/'host','--output-on-failure'])
    dependencies = run(['readelf','-d',BUILD/'host/own-rt-smoke'])
    assert all(word not in dependencies.lower() for word in ['libsycl','libze_loader','libur_loader','libopencl'])
    receipt['mock_smoke'] = json.loads((BUILD/'host/mock-smoke.json').read_text())
    receipt['mock_census'] = json.loads((BUILD/'host/mock-smoke.json.census.json').read_text())
    receipt['compile_commands'] = {mode: json.loads((BUILD/mode/'compile_commands.json').read_text()) for mode in ['host','sycl']}
    assert all('-fsycl' not in row['command'] for row in receipt['compile_commands']['host'])
    assert all('-fsycl' in row['command'] for row in receipt['compile_commands']['sycl'])
    assert not (BUILD/'sycl/own-rt-smoke').exists()
    receipt['host_ctest_count'] = 12
    receipt['level_zero_header_sha256'] = hashlib.sha256(Path('/usr/include/level_zero/ze_api.h').read_bytes()).hexdigest()
    receipt['passed'] = True
finally:
    receipt['source_sha256'] = {str(p.relative_to(HERE)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in sorted(HERE.rglob('*')) if p.is_file() and BUILD not in p.parents and p.name!='build-receipt.json'}
    # Only this packet's ignored outputs; unrelated experiment scratch is untouched.
    if BUILD.exists():
        shutil.rmtree(BUILD)
    receipt['build_directory_removed'] = not BUILD.exists()
    (HERE/'build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
