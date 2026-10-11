#!/usr/bin/env python3
"""Build SYCL, execute host tests only, retain receipts and remove own scratch."""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
BUILD = HERE / 'build'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--keep-build', action='store_true', help='retain prepared inputs for coordinator')
    parser.add_argument('--build-dir', type=Path, default=BUILD,
                        help='fresh CPU build directory; may be a child of build to preserve device evidence')
    args = parser.parse_args()
    if os.getpriority(os.PRIO_PROCESS, 0) != 19 or os.environ.get('OMP_NUM_THREADS') != '2':
        parser.error('nice19 and OMP_NUM_THREADS=2 required')
    build = args.build_dir.absolute()
    if build != BUILD and BUILD not in build.parents:
        parser.error('build directory must be within packet10/build')
    if build.resolve() != build or (build != BUILD and args.keep_build):
        parser.error('no symlink build directory; alternate CPU scratch cannot be retained for device admission')
    if build.exists() or build.is_symlink():
        parser.error('build must be new; preserve existing coordinator evidence before cleanup')
    build.mkdir(parents=True)
    env = dict(os.environ, PACKET10_CPU_BUILD=str(build))
    receipt = dict(schema='own-runtime.iq3.packet10.cpu-build.v1', passed=False,
        date_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), device_executed=False,
        commands=[], scratch_removed=False)
    def run(argv):
        argv = list(map(str, argv))
        result = subprocess.run(argv, capture_output=True, text=True, env=env)
        receipt['commands'].append(dict(argv=argv, returncode=result.returncode,
                                       stdout=result.stdout, stderr=result.stderr))
        print(result.stdout, end='', flush=True)
        print(result.stderr, end='', flush=True)
        if result.returncode:
            raise RuntimeError('CPU command failed: ' + str(argv))
        return result.stdout
    try:
        run(['cmake', '-S', HERE, '-B', build / 'device', '-DCMAKE_BUILD_TYPE=Release'])
        run(['cmake', '--build', build / 'device', '-j2'])
        # No native target is invoked here, including help/version.
        dependencies = run(['readelf', '-d', build / 'device/host-tests'])
        if any(name in dependencies.lower() for name in ('libsycl', 'libze_loader', 'libur_loader', 'libopencl')):
            raise RuntimeError('host executable has device dependencies')
        run([sys.executable, '-B', HERE / 'analysis.py'])
        run([sys.executable, '-B', HERE / 'tests/test_protocol.py'])
        run(['/home/steve/.venvs/vllm-xpu/bin/python', '-B', HERE / 'tests/prepare.py'])
        receipt['prepared'] = json.loads((build / 'prepared.json').read_text())
        receipt['compile_commands'] = json.loads((build / 'device/compile_commands.json').read_text())
        receipt['passed'] = True
    except Exception as exc:
        receipt['error'] = str(exc)
    finally:
        if not args.keep_build:
            shutil.rmtree(build)
            receipt['scratch_removed'] = True
        (HERE / 'build-receipt.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n')
    return 0 if receipt['passed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
