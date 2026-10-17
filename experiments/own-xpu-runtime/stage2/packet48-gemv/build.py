#!/usr/bin/env python3
"""Small, serial CPU-only compilation; never executes a device binary."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FLAGS = ['-std=c++20', '-O2', '-fno-fast-math', '-ffp-contract=off', '-Werror=return-type']
INCLUDES = [HERE.parent / 'packet45-merged3', HERE.parent.parent / 'stage1/packet3-prep/src',
            HERE.parent / 'packet2/kernels', HERE.parent / 'packet2/loader']

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def limits():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19, 'nice 19 required'
    assert set(os.sched_getaffinity(0)) <= set(range(4,16)) | set(range(20,32)), 'CPU affinity'
    assert shutil.disk_usage(HERE).free > 8_000_000_000 + 512*1024**2, 'disk budget'

def run(kind):
    limits()
    import fcntl
    build = HERE / 'build' / kind
    build.mkdir(parents=True, exist_ok=True)
    with (HERE / 'build/cpu-work.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        compiler = '/usr/bin/g++' if kind == 'gnu' else '/opt/intel/oneapi/compiler/2026.0/bin/icpx'
        flags = FLAGS + [item for p in INCLUDES for item in ['-I', str(p)]]
        flags += ['-fsycl', '-fdenormal-fp-math=ieee', '-foffload-fp32-prec-div', '-foffload-fp32-prec-sqrt'] if kind == 'device' else ['-DOWN_RT_HOST_ONLY']
        targets = ['bench'] if kind == 'device' else ['bench', 'gemv_cpu_test']
        sources, artifacts, commands = {}, {}, []
        version = subprocess.check_output([compiler, '--version'], text=True)
        for name in targets:
            source = HERE / (name+'.cpp')
            dep_command = [compiler, *flags, '-MM', str(source)]
            raw = subprocess.check_output(dep_command, text=True)
            (build/(name+'.dependencies.txt')).write_text(raw)
            # icpx -fsycl emits both host/device make rules inside an offload
            # bundle. Keep their union; bundle marker comments are not paths.
            paths=set()
            for line in raw.replace('\\\n',' ').splitlines():
                if not line.strip() or line.lstrip().startswith('#'): continue
                assert ':' in line, 'unexpected dependency output'
                paths.update(shlex.split(line.split(':',1)[1]))
            pins = {str(Path(p).resolve().relative_to(ROOT)): sha(p) for p in paths}
            for p, h in pins.items():
                assert p not in sources or sources[p] == h, 'source changed mid-build'
            sources.update(pins)
            command = [compiler, *flags, str(source), '-o', str(build/name), '-lcrypto']
            if kind == 'device':
                command += ['-lze_loader', '-Wl,-rpath,/opt/intel/oneapi/compiler/2026.0/lib']
            commands.append(command)
            with (build/(name+'.build.log')).open('w') as log:
                subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT)
            artifacts[str((build/name).relative_to(HERE))] = sha(build/name)
        assert all(sha(ROOT/p) == h for p,h in sources.items()), 'compiled source drift'
        sources[str((HERE/'build.py').relative_to(ROOT))] = sha(HERE/'build.py')
        row = dict(schema='ownrt.packet48.build.v1', passed=True, device_executed=False,
                   kind=kind, compiler=compiler, compiler_sha256=sha(compiler), compiler_version=version,
                   sources=sources, artifacts=artifacts, commands=commands, completed_unix=time.time(),
                   affinity=sorted(os.sched_getaffinity(0)), nice=19,
                   disk_bytes=sum(p.stat().st_size for p in build.rglob('*') if p.is_file()))
        (HERE/f'build-{kind}.json').write_text(json.dumps(row,indent=2)+'\n')
        print(json.dumps(dict(kind=kind, passed=True, device_executed=False, disk_bytes=row['disk_bytes'])))

if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--kind',required=True,choices=['gnu','intel','device'])
    run(p.parse_args().kind)
