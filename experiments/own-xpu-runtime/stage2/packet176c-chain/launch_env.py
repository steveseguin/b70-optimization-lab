"""Shared, versioned native loader environment for new packets.

Recorded source: stage2/packet139-record-bundle/v5/launch-environment.json
SHA256: 2da93bdd5d1710921807afd69d2ba1c7399e9a95b38c65edb22927f3fcf5e95a
Also used by packet58x's library-path.json (working October 18 windows).
The tuple is the source of truth; do not source a shell or inherit LD_*.
Import this file, or vendor it and retain this provenance. Frozen packets
are intentionally not rewritten. `python3 -B launch_env.py BINARY ...`
checks each ELF's loader dependencies under exactly this environment.
"""
import argparse
from pathlib import Path
import re

ONEAPI_ROOT = Path('/opt/intel/oneapi')
# Preserve the recorded order and spelling, including the duplicate tcm path.
LIBRARY_COMPONENTS = (
    'tcm/1.5/lib', 'umf/1.1/lib', 'tcm/1.5/env/../lib',
    'tbb/2023.0/env/../lib/intel64/gcc4.8', 'pti/1.0/lib',
    'mkl/2026.0/lib', 'dnnl/2026.0/lib', 'debugger/2026.0/opt/debugger/lib',
    'compiler/2026.0/opt/compiler/lib', 'compiler/2026.0/lib',
)


def library_path(root=ONEAPI_ROOT):
    return ':'.join(str(Path(root) / part) for part in LIBRARY_COMPONENTS)


def environment():
    return dict(PATH='/usr/bin:/bin', OMP_NUM_THREADS='2', LD_LIBRARY_PATH=library_path())


def env_command(argv, env=None):
    env = environment() if env is None else env
    if set(env) != {'PATH', 'OMP_NUM_THREADS', 'LD_LIBRARY_PATH'}:
        raise ValueError('native environment must contain exactly the three lanequeue keys')
    if any(not isinstance(v, str) or '\x00' in v or '\n' in v for v in env.values()):
        raise ValueError('invalid environment value')
    return ['/usr/bin/env', '-i', *[f'{k}={v}' for k, v in env.items()], *map(str, argv)]


def check_binary(binary, env=None, runner=None):
    """Fail on missing libraries even when ldd exits zero. Never print its text."""
    if runner is None:
        from entry_sandbox import run
        runner = run
    path = Path(binary).resolve(strict=True)
    with path.open('rb') as stream:
        if stream.read(4) != b'\x7fELF':
            raise ValueError('native binary is not ELF')
    result = runner(env_command(['/usr/bin/ldd', str(path)], env), binary=path)
    output = result.stdout + result.stderr
    missing = re.findall(r'^\s*([\w.+-]+)\s*=>\s*not found\s*$', output, re.M)
    return dict(passed=result.returncode == 0 and 'not found' not in output,
                returncode=result.returncode, missing=missing)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('binaries', nargs='+', type=Path)
    args = ap.parse_args()
    passed = True
    for binary in args.binaries:
        try:
            row = check_binary(binary)
            ok = row['passed']
            detail = ', '.join(row['missing']) or 'loader check'
        except (OSError, ValueError, RuntimeError):
            ok, detail = False, 'binary or sandbox unavailable'
        print(f'{"PASS" if ok else "FAIL"} {binary.name}: {detail}')
        passed &= ok
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
