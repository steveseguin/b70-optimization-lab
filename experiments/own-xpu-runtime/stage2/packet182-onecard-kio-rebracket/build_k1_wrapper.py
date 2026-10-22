#!/usr/bin/env python3
"""Packet182: rebuild only the K1 exec wrapper (build/device/p58-cache-fixtures).

The device engine (build/device/own-rt-iq3), the K1 core and the host binaries are
byte copies of packet176's sealed artifacts (lineage/packet182-copy.json). The
16 KB wrapper is the one artifact whose bytes name its packet: it execv()s
<packet>/build/device/p58-cache-fixtures-core by absolute path, so packet176's copy
would run packet176's core. One g++ -O2 compile of native/k1_help.cpp (path
rewritten) inside the shared ops compile turn; the wrapper is then run with --help
only (it prints its option list and exits before any execv).
CPU only:  nice -n 19 taskset -c 8-15,24-31 python3 -B build_k1_wrapper.py < /dev/null
"""
import hashlib, importlib.util, json, os, resource, shutil, subprocess
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
OUT = P / 'build/device/p58-cache-fixtures'
CORE = P / 'build/device/p58-cache-fixtures-core'


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    assert shutil.disk_usage('/').free >= 27_000_000_000, 'CPU stop: 27 GB root floor'
    src = P / 'native/k1_help.cpp'
    text = src.read_text()
    assert text.count(str(CORE)) == 1 and 'packet176' not in text, 'wrapper must exec this packet core only'
    copy = json.loads((P / 'lineage/packet182-copy.json').read_text())
    assert copy['packet176_sealed_artifacts']['build/device/p58-cache-fixtures-core'] == sha(CORE), 'core is not packet176 sealed bytes'
    spec = importlib.util.spec_from_file_location('compile_turn', ROOT / 'experiments/own-xpu-runtime/ops/compile_turn.py')
    turn = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(turn)
    command = ['/usr/bin/g++', '-O2', str(src), '-o', str(OUT)]
    with turn.turn(), (P / 'build/k1-help.log').open('w') as log:
        subprocess.run(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, check=True,
                       preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3)))
    raw = OUT.read_bytes()
    assert raw.count(str(CORE).encode()) == 1 and b'packet176' not in raw
    helped = subprocess.run([str(OUT), '--help'], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30,
                            env=dict(PATH='/usr/bin:/bin'))
    assert helped.returncode == 0 and '--output' in helped.stdout.split()
    row = dict(schema='packet182.k1-wrapper.v1', passed=True, device_executed=False, command=command,
               source_sha256=sha(src), wrapper_sha256=sha(OUT), execs=str(CORE.relative_to(ROOT)), core_sha256=sha(CORE),
               packet176_wrapper_sha256=copy['packet176_sealed_artifacts']['build/device/p58-cache-fixtures'],
               help_stdout=helped.stdout.strip(), compile_turn='ops/compile_turn.turn()', native_binaries_executed=['wrapper --help only'])
    (P / 'evidence').mkdir(exist_ok=True)
    (P / 'evidence/k1-wrapper.json').write_text(json.dumps(row, indent=2) + '\n')
    print(json.dumps(dict(passed=True, wrapper_sha256=row['wrapper_sha256'])))


if __name__ == '__main__':
    main()
