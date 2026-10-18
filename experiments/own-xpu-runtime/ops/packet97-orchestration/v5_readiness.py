"""Collect all completed v5 brackets without pooling different native identities."""
import json
from pathlib import Path
import subprocess
import sys

from v5_jobs import V5, O, ROOT, ORDER, sha

FIELDS = ('selection_sha256', 'binary_sha256', 'seal_sha256', 'dispatch_sha256',
          'memory_plan_sha256', 'profile', 'timing', 'placement')


def identity_matches(identity, expected):
    views = identity.get('bracket', {}).get('views', [])
    if [view.get('choice') for view in views] != list(ORDER):
        return False
    return all(all(actual.get(key) == expected[view['choice']].get(key)
                   and key in actual and key in expected[view['choice']] for key in FIELDS)
               for view in views
               for actual in [dict(identity, selection_sha256=view.get('selection_sha256'))])


def collect(expected):
    brackets, excluded, receipts = [], [], {}
    for path in sorted((V5/'evidence').glob('*/window.json')):
        window = json.loads(path.read_text())
        if not window.get('finished_utc_ns') or window.get('child_still_running'):
            continue
        root = path.parent
        identity = json.loads((root/'identity.json').read_text())
        if identity.get('bracket', {}).get('kind') != 'bracket':
            continue
        views = identity['bracket'].get('views', [])
        # Like packet97d's decision enumeration, unrelated selections are not
        # attempts at this composition. Equal bytes with another binary/seal
        # are retained as exclusions instead of being silently pooled.
        if not views or any(view.get('selection_sha256') !=
                            expected.get(view.get('choice'), {}).get('selection_sha256')
                            for view in views):
            continue
        lane = window.get('lane')
        assert lane in ('A', 'B'), 'invalid completed v5 lane'
        entry = dict(wrapper='v5', lane=lane, output=str(root),
                     shared_model_lifetime=True)
        if not identity_matches(identity, expected):
            excluded.append(dict(entry, reason='selection/binary/baseline/seal identity differs'))
            continue
        cp = subprocess.run([sys.executable, '-B', str(O/'v5_evidence.py'), str(root)],
                            cwd=ROOT, stdin=subprocess.DEVNULL, capture_output=True,
                            text=True, timeout=240)
        if cp.returncode:
            entry['error'] = 'v5 receipt verification failed: '+cp.stderr[-2000:]
        else:
            entry.update(json.loads(cp.stdout))
        brackets.append(entry)
        for receipt in sorted(root.rglob('*.json')):
            receipts[str(receipt.relative_to(ROOT))] = sha(receipt)
    return brackets, excluded, receipts
