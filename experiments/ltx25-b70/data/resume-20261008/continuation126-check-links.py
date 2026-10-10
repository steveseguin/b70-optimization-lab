#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Repository checks plus the new lane documents; no live operations."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).with_name('continuation126-tests')
LANE = 'experiments/ltx25-b70/'
commands = {
 'doc-links-final.log': [
  [sys.executable,'-B','tools/check-doc-links.py'],
  [sys.executable,'-B','tools/check-doc-links.py',
   LANE+'notes/2026-10-10-continuation123b-regression.md',
   LANE+'notes/2026-10-10-continuation126-stream-design.md',
   LANE+'recovery/20261010-continuation126-stream/CONTRACT.md',
   LANE+'recovery/20261010-continuation126-stream/LAUNCH.md']],
 'manifest-paths-final.log': [[sys.executable,'-B','tools/check-manifest-paths.py']]}
rows = {}
for name, calls in commands.items():
    results = [subprocess.run(c, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT) for c in calls]
    log = OUT/name
    log.write_text(''.join(r.stdout for r in results))
    rows[name] = {'commands':calls,'returncode':max(r.returncode for r in results),
                  'sha256':hashlib.sha256(log.read_bytes()).hexdigest()}
(OUT/'integrity-validation.json').write_text(json.dumps(rows,indent=2,sort_keys=True)+'\n')
print(json.dumps(rows))
assert all(r['returncode']==0 for r in rows.values()), rows
