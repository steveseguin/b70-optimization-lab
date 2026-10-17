#!/usr/bin/env python3
"""CPU-only coordinator admission tests; no native launch or discovery."""
import json
import os
from pathlib import Path
import subprocess
import sys
from window_support import HERE, REPO, require, sha


def main():
    require(os.getpriority(os.PRIO_PROCESS, 0) == 19, 'nice 19 required')
    require(set(os.sched_getaffinity(0)) <= set(range(4,16)) | set(range(20,32)), 'CPU affinity required')
    command = [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(HERE), '-p', 'test_*.py', '-v']
    result = subprocess.run(command, capture_output=True, text=True)
    sources = [p for p in HERE.glob('*.py')]
    sources += [REPO/'experiments/own-xpu-runtime/stage2/packet34-replay-bench/window.py']
    row = dict(schema='own-runtime.packet47.python-gates.v1', passed=result.returncode == 0,
               device_executed=False, sources={str(p.relative_to(REPO)):sha(p) for p in sources},
               command=command, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
    (HERE/'python-gates.json').write_text(json.dumps(row,indent=2)+'\n')
    print(result.stderr, end='')
    return result.returncode

if __name__ == '__main__':
    raise SystemExit(main())
