#!/usr/bin/env python3
"""Safety / exec-limits / loader gate (CPU only; --help is the only native execution).

- launch_env.py: every ELF the proposal declares resolves its loader dependencies under exactly the
  recorded closed environment (PATH, OMP_NUM_THREADS, LD_LIBRARY_PATH from library-path.json);
- exec_limits: the native launch path refuses a finite RLIMIT_AS and any limit change before exec;
- the engine's --help lists the new capacity dimension and the fixed kernel foreground I/O flag;
- the engine refuses unknown flags and an unknown capacity before any allocation (parser only).
Writes evidence/loader.json.
"""
import json, os, subprocess, sys
from pathlib import Path
from build_engine import P, ROOT, sha, save, limits


def main():
    limits()
    lib = json.loads((P / 'library-path.json').read_text())['LD_LIBRARY_PATH']
    from launch_env import library_path, environment
    assert lib == library_path(), 'recorded library path differs from launch_env'
    binaries = [P / 'build/device/own-rt-iq3', P / 'build/device/p58-cache-fixtures', P / 'build/device/p58-cache-fixtures-core', P / 'build/gnu-host/own-rt-iq3']
    # The vendored launch_env CLI imports ops/entry_sandbox for the isolated ldd child.
    cp = subprocess.run([sys.executable, '-B', str(P / 'launch_env.py'), *map(str, binaries)], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=300, cwd=ROOT,
                        env=dict(os.environ, PYTHONPATH=str(P.parents[1] / 'ops')))
    assert cp.returncode == 0, cp.stdout[-2000:] + cp.stderr[-2000:]
    env = environment()
    helps = {}
    for b in binaries[:2]:
        h = subprocess.run([str(b), '--help'], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30, env=env)
        assert h.returncode == 0, b
        helps[str(b.relative_to(P))] = h.stdout.strip()
    assert '--cache-cap 18GB|max|max23 (default:max)' in helps['build/device/own-rt-iq3'] and '--foreground-io copy|kernel (default:copy)' in helps['build/device/own-rt-iq3']
    assert '--output' in helps['build/device/p58-cache-fixtures'].split()
    # Parser refusals on the host binary (no device, no allocation): unknown flag, unknown capacity.
    host = P / 'build/gnu-host/own-rt-iq3'
    refusals = []
    for extra, needle in ((['--no-such-flag', 'x'], ''), (['--cache-cap', 'max24'], 'capacity')):
        r = subprocess.run([str(host), '--p58r-parse-test', '--output', '/nonexistent/p58c23', *extra], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30, env=env)
        assert r.returncode != 0, extra
        refusals.append(dict(argv=extra, returncode=r.returncode, stderr=r.stderr.strip()[-200:]))
    from exec_limits import check, snapshot
    before = snapshot(); check(); assert snapshot() == before
    save(P / 'evidence/loader.json', dict(passed=True, device_executed=False, schema='packet58cache23.loader.v1',
         environment=dict(PATH=env['PATH'], OMP_NUM_THREADS=env['OMP_NUM_THREADS'], LD_LIBRARY_PATH='<library-path.json>'),
         binaries={str(b.relative_to(P)): sha(b) for b in binaries}, launch_env_stdout=cp.stdout.strip()[-3000:], helps=helps, parser_refusals=refusals,
         exec_limits='RLIMIT_AS unlimited required at exec; limits unchanged across the check', native_executed=['--help', '--p58r-parse-test refusals (host binary)']))
    print(json.dumps(dict(passed=True, binaries=len(binaries), refusals=len(refusals))))


if __name__ == '__main__':
    main()
