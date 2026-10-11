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
    args = parser.parse_args()
    if os.getpriority(os.PRIO_PROCESS, 0) != 19 or os.environ.get('OMP_NUM_THREADS') != '2':
        parser.error('nice19 and OMP_NUM_THREADS=2 required')
    if BUILD.exists() or BUILD.is_symlink():
        parser.error('build must be new; preserve existing coordinator evidence before cleanup')
    BUILD.mkdir()
    receipt = dict(schema='own-runtime.iq3.packet9.cpu-build.v1', passed=False,
        date_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), device_executed=False,
        commands=[], scratch_removed=False)
    def run(argv):
        argv = list(map(str, argv))
        result = subprocess.run(argv, capture_output=True, text=True)
        receipt['commands'].append(dict(argv=argv, returncode=result.returncode,
                                       stdout=result.stdout, stderr=result.stderr))
        print(result.stdout, end='', flush=True)
        print(result.stderr, end='', flush=True)
        if result.returncode:
            raise RuntimeError('CPU command failed: ' + str(argv))
        return result.stdout
    try:
        run(['cmake', '-S', HERE, '-B', BUILD / 'device', '-DCMAKE_BUILD_TYPE=Release'])
        run(['cmake', '--build', BUILD / 'device', '-j2'])
        # No native target is invoked here, including help/version.
        dependencies = run(['readelf', '-d', BUILD / 'device/host-tests'])
        if any(name in dependencies.lower() for name in ('libsycl', 'libze_loader', 'libur_loader', 'libopencl')):
            raise RuntimeError('host executable has device dependencies')
        run([sys.executable, '-B', HERE / 'analysis.py'])
        run([sys.executable, '-B', HERE / 'tests/test_protocol.py'])
        run([sys.executable, '-B', HERE / 'tests/prepare.py'])
        receipt['prepared'] = json.loads((BUILD / 'prepared.json').read_text())
        receipt['compile_commands'] = json.loads((BUILD / 'device/compile_commands.json').read_text())
        receipt['passed'] = True
    except Exception as exc:
        receipt['error'] = str(exc)
    finally:
        if not args.keep_build:
            shutil.rmtree(BUILD)
            receipt['scratch_removed'] = True
        (HERE / 'build-receipt.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n')
    return 0 if receipt['passed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
