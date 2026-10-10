#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Full client regression suite; audited CPU fakes only, never a model server."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[2]
TESTS = LANE / 'stream/tests'
OUT = LANE / 'data/resume-20261008/continuation126-tests'
SUITES = ['112', '113', '114', '115', '116', '116b', '117', '118', '118b',
          '119', '119_integration', '120', '120_integration', '121', '121_integration',
          '122', '122_integration', '123', '123_integration', '123b', '123b_integration', '124', '124_integration', '125', '125_integration', '126', '126_integration']
rows = []
for suite in SUITES:
    log = OUT / ('client-' + suite + '-final.log')
    with log.open('x') as stream:
        result = subprocess.run([sys.executable, '-B', str(TESTS / 'run_cpu_suites.py'),
                                 'run_tests_' + suite + '.py'], stdout=stream, stderr=subprocess.STDOUT,
                                env=dict(os.environ, OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', PYTHONDONTWRITEBYTECODE='1'))
    text = log.read_text()
    match = re.findall(r'(\d+)/(\d+) passed', text)
    passed, count = map(int, match[-1]) if match else (0, 0)
    row = dict(suite=suite, returncode=result.returncode, passed=passed, count=count,
               log=log.name, sha256=hashlib.sha256(log.read_bytes()).hexdigest())
    rows.append(row)
    (OUT / 'client-progress.json').write_text(json.dumps(rows, indent=2)+'\n')
    print(row, flush=True)
raise SystemExit(any(row['returncode'] or not row['count'] or row['passed'] != row['count'] for row in rows))
