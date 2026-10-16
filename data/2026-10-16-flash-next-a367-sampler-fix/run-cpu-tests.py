#!/usr/bin/env python3
"""Run the four CPU regression suites and retain logs/counts without old receipt edits."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PREP = REPO / 'experiments/own-xpu-runtime/stage1/packet4-prep'
assert os.getpriority(os.PRIO_PROCESS, 0) == 19
assert os.sched_getaffinity(0) <= set(range(4, 16)) | set(range(20, 32))
env = dict(os.environ, OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2',
           PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=f'{PREP}:{PREP / "driver"}')
suites = [
    ('calibration', '/usr/bin/python3', PREP / 'a367-calibrate', 'test_calibrate.py'),
    ('driver', '/home/steve/.venvs/vllm-xpu/bin/python3', PREP / 'driver', 'test_driver.py'),
    ('payload', '/usr/bin/python3', REPO / 'scripts', 'test_verify_flash_next_a367_launch_payload.py'),
    ('frozen-tree', '/usr/bin/python3', REPO / 'scripts', 'test_verify_qwen38_flash_next_fp8_tree.py'),
]
rows = []
for name, python, directory, pattern in suites:
    command = [python, '-B', '-m', 'unittest', 'discover', '-s', str(directory), '-p', pattern, '-v']
    result = subprocess.run(command, cwd=REPO, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log = result.stdout
    (HERE / f'{name}.log').write_text(log)
    match = re.search(r'Ran (\d+) tests? in', log)
    count = int(match[1]) if match else 0
    row = dict(suite=name, command=command, tests=count, returncode=result.returncode,
               passed=result.returncode == 0 and count > 0 and '\nOK\n' in log,
               failures=len(re.findall(r'^FAIL: ', log, re.M)), errors=len(re.findall(r'^ERROR: ', log, re.M)),
               skips=len(re.findall(r" \.\.\. skipped ", log)), log=f'{name}.log',
               log_sha256=hashlib.sha256(log.encode()).hexdigest())
    rows.append(row)
    print(json.dumps(row), flush=True)
receipt = dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
               suites=rows, tests=sum(r['tests'] for r in rows), passed=all(r['passed'] for r in rows),
               nice=19, affinity=sorted(os.sched_getaffinity(0)), native_executed=False)
(HERE / 'cpu-tests.json').write_text(json.dumps(receipt, indent=2) + '\n')
sys.exit(not receipt['passed'])
