#!/usr/bin/env python3
"""CPU validation and compile/link; never invoke a device binary."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--keep-build', action='store_true')
    args = p.parse_args()
    if os.getpriority(os.PRIO_PROCESS, 0) != 19 or os.environ.get('OMP_NUM_THREADS') != '2':
        raise SystemExit('nice 19 and OMP_NUM_THREADS=2 required')
    build = HERE/'build'
    scratch = [build/'owner', build/'compile']
    if any(x.exists() for x in scratch):
        raise SystemExit('owned scratch exists; preserve existing run/build evidence first')
    record = dict(schema='own-runtime.peer.build.v1', passed=False, native_executed=False,
                  timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(), commands=[])
    paths = sorted([x for x in HERE.iterdir() if x.suffix in ('.cpp', '.hpp', '.py', '.txt', '.json')
                    and x.name != 'build-receipt.json'] + [HERE.parent/'packet2/tests/device_window.py'])
    record['source_sha256'] = {str(x.relative_to(ROOT)): sha(x) for x in paths}
    def run(argv):
        q = subprocess.run(argv, cwd=HERE, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        record['commands'].append(dict(argv=argv, returncode=q.returncode, output=q.stdout))
        print(q.stdout, end='', flush=True)
        if q.returncode:
            raise RuntimeError('command failed: '+str(argv))
        return q.stdout
    try:
        (build/'owner').mkdir(parents=True)
        pin = json.loads((HERE/'owner-source.json').read_text())
        for name, item in pin['files'].items():
            data = subprocess.check_output(['git', 'show', pin['commit']+':'+item['path']], cwd=ROOT)
            (build/'owner'/name).write_bytes(data)
            if sha(build/'owner'/name) != item['sha256']:
                raise RuntimeError('pinned owner hash mismatch')
        run([sys.executable, '-B', '-m', 'unittest', '-v', 'test_packet'])
        run(['cmake', '-S', str(HERE), '-B', str(build/'compile'), '-DCMAKE_BUILD_TYPE=Release'])
        run(['cmake', '--build', str(build/'compile'), '-j2'])
        elf = run(['readelf', '-d', str(build/'compile/host-tests')])
        if any(x in elf.lower() for x in ('libsycl', 'ze_loader', 'libur_', 'libopencl')):
            raise RuntimeError('CPU executable links a device runtime')
        first = run([str(build/'compile/host-tests')])
        if run([str(build/'compile/host-tests')]) != first:
            raise RuntimeError('fresh CPU process differs')
        record['binary_sha256'] = sha(build/'compile/peer-native')
        record['compile_commands'] = json.loads((build/'compile/compile_commands.json').read_text())
        for name, digest in record['source_sha256'].items():
            if sha(ROOT/name) != digest:
                raise RuntimeError('concurrent source change: '+name)
        record['passed'] = True
    finally:
        if not args.keep_build:
            for x in scratch:
                if x.exists():
                    shutil.rmtree(x)
            if build.exists() and not any(build.iterdir()):
                build.rmdir()
        record['scratch_removed'] = not any(x.exists() for x in scratch)
        (HERE/'build-receipt.json').write_text(json.dumps(record, indent=2)+'\n')

if __name__ == '__main__':
    main()
