#!/usr/bin/env python3
"""Short standard-library contract tests only; no native process or device."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from preparation import limits

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def sources():
    files = [*HERE.glob('*.py'), *HERE.glob('*.sh'), *HERE.joinpath('diagnostics').glob('*.py'),
             HERE.parent / 'packet34-replay-bench/window.py']
    return {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}


def main():
    admission = limits(heavy=False)
    before = sources()
    results = []
    for path, pattern in ((HERE, 'test_cache_budget.py'), (HERE, 'test_window.py'),
                          (HERE / 'diagnostics', 'test_validate.py')):
        command = [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(path), '-p', pattern, '-v']
        result = subprocess.run(command, text=True, capture_output=True, timeout=30)
        results.append(dict(command=command, returncode=result.returncode,
                            stdout=result.stdout, stderr=result.stderr))
        if result.returncode:
            break
    if before != sources():
        raise RuntimeError('CPU test source changed during checks')
    receipt = dict(schema='own-runtime.packet46.python-gates.v1',
                   passed=len(results) == 3 and all(row['returncode'] == 0 for row in results),
                   device_executed=False, sources=before, admission=admission, results=results,
                   completed_utc=datetime.now(timezone.utc).isoformat())
    (HERE / 'python-gates.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(dict(passed=receipt['passed'], suites=len(results), device_executed=False)))
    return 0 if receipt['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
