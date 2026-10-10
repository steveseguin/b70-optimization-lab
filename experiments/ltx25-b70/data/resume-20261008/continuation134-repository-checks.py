#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Static repository checks; never executes either launch wrapper."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
LANE = HERE.parents[1]
REPO = LANE.parents[1]
OUT = HERE / 'continuation134-tests'
AUTHOR = LANE / 'recovery/20261010-continuation134-stream'
assert sys.executable == '/home/steve/.venvs/ltx25-baseline/bin/python'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

rows = []
commands = [
    ('doc-links', [sys.executable, '-B', 'tools/check-doc-links.py']),
    ('packet-doc-links', [sys.executable, '-B', 'tools/check-doc-links.py',
        str(LANE / 'notes/2026-10-10-continuation133b-results-145.md'),
        str(LANE / 'notes/2026-10-10-continuation134-stream-design.md'),
        str(AUTHOR / 'CONTRACT.md'), str(AUTHOR / 'LAUNCH.md')]),
    ('manifest-paths', [sys.executable, '-B', 'tools/check-manifest-paths.py']),
    ('launch-shell-syntax', ['bash', '-n', str(AUTHOR / 'launch-134.sh')]),
    ('client-shell-syntax', ['bash', '-n', str(LANE / 'stream/start-client-134.sh')]),
]
for label, command in commands:
    path = OUT / (label + '-final.log')
    with path.open('w') as log:
        result = subprocess.run(command, cwd=REPO, stdout=log, stderr=subprocess.STDOUT)
    rows.append(dict(label=label, command=command, returncode=result.returncode,
                     log=str(path.relative_to(REPO)), sha256=sha(path)))

pinlog = OUT / 'check-pinned-hashes.log'
raw = pinlog.read_text()
pin_summary = 'checked 318 literal file pins: 87 match, 231 drifted, 0 target absent'
assert pin_summary in raw
drifts = [line for line in raw.splitlines() if line.startswith('  DRIFT')]
assert drifts and all('experiments/qwen38-flash-next-fp8-b70/' in line for line in drifts)
passed = all(row['returncode'] == 0 for row in rows)
record = dict(status='packet134-checks-passed-existing-pin-drift' if passed else 'failed',
    checks=rows, pinned_hashes=dict(returncode=1, summary=pin_summary,
        scope='All reported drift belongs to pre-existing Flash-Next pins; no packet134 drift is reported.',
        log=str(pinlog.relative_to(REPO)), sha256=sha(pinlog)),
    launchers_executed=False)
(OUT / 'repository-checks.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record))
raise SystemExit(not passed)
