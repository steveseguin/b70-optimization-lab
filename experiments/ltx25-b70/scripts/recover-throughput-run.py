#!/usr/bin/env python3
"""Finish a throughput run whose driver died mid-poll: fetch each prompt's history
by the saved prompt id, write history/result, then rerun the driver's oracle and
interval logic by re-invoking run-throughput-fixtures' post-processing."""
import json, sys, time, urllib.request
from pathlib import Path
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913'); API = 'http://127.0.0.1:8188'
prefix, count = sys.argv[1], int(sys.argv[2])
missing = 0
for i in range(count):
    name = f'{prefix}-{i:02d}'; req = ROOT / 'requests' / name
    if (req / 'history.json').is_file() and (req / 'history.json').stat().st_size:
        continue
    pid = json.loads((req / 'submission.json').read_text())['prompt_id']
    with urllib.request.urlopen(API + '/history/' + pid, timeout=300) as r:
        h = json.loads(r.read())
    entry = h.get(pid)
    if not entry or not entry.get('status', {}).get('completed'):
        missing += 1; continue
    (req / 'history.json').write_text(json.dumps(entry, indent=2) + '\n')
    st = entry['status']; ts = {m[0]: m[1]['timestamp'] for m in st['messages'] if isinstance(m[1], dict) and 'timestamp' in m[1]}
    (req / 'result.json').write_text(json.dumps({'name': name, 'prompt_id': pid,
        'seconds': (ts['execution_success'] - ts.get('execution_start', ts['execution_success'])) / 1000, 'status': st}, indent=2) + '\n')
print(json.dumps({'prefix': prefix, 'count': count, 'still_missing': missing}))
