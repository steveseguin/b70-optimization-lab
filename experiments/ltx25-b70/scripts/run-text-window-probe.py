#!/usr/bin/env python3
"""Submit packet 93's text-window qualification probe once and report its outcome.

Exit 0: window-qualified ('pipeline-window' admitted on this server).
Exit 10: a valid negative outcome (window-not-deterministic, window-not-close,
         window-capture-proof-failed, insufficient-memory); the window arms
         must be skipped, the server is healthy and the window graphs released.
Exit 1: the probe did not complete or its receipt is missing/unreadable.
No retries. Writes prompt/submission/history under R/requests/<name>/.
The window changes output at rounding level; owner approved 2026-10-04 on two conditions
(negligible finished-clip difference; new references, byte-identical thereafter).
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
API = 'http://127.0.0.1:8188'
NEGATIVE = ('window-not-deterministic', 'window-not-close', 'window-capture-proof-failed', 'insufficient-memory')

ap = argparse.ArgumentParser()
ap.add_argument('name')
ap.add_argument('--graph', required=True)
ap.add_argument('--server-run', required=True)
ap.add_argument('--timeout', type=int, default=1500)
a = ap.parse_args()
if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,100}', a.name):
    raise SystemExit('name must be lowercase [a-z0-9-]')
run = Path(a.server_run)


def call(path, payload=None):
    assert not (ROOT / 'FAULT.json').exists(), 'device fault; halt requests'
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(API + path, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b'{}')


graph = json.loads(Path(a.graph).read_text())
assert graph['470']['class_type'] == 'LTXTextWindowProbe'
for node in graph.values():
    if 'run_name' in node.get('inputs', {}):
        node['inputs']['run_name'] = a.name
queue = call('/queue')
assert not queue['queue_running'] and not queue['queue_pending'], 'server busy'
req = ROOT / 'requests' / a.name
req.mkdir(parents=True, exist_ok=False)
(req / 'prompt.json').write_text(json.dumps(graph, indent=2) + '\n')
r = call('/prompt', {'prompt': graph, 'client_id': 'probe-' + a.name})
assert not r.get('node_errors'), r
(req / 'submission.json').write_text(json.dumps(r, indent=2) + '\n')
deadline = time.time() + a.timeout
entry = None
while time.time() < deadline:
    try:
        entry = call('/history/' + r['prompt_id']).get(r['prompt_id'])
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        entry = None          # the web loop can stall while workers capture graphs
    if entry and entry.get('status', {}).get('completed') is not None:
        if entry['status'].get('completed') or any(m[0] == 'execution_error' for m in entry['status'].get('messages', [])):
            break
    time.sleep(2)
if entry is not None:
    (req / 'history.json').write_text(json.dumps(entry, indent=2) + '\n')
receipt = run / ('text-window-probe-' + a.name + '.json')
if not receipt.is_file():
    print('probe receipt missing:', receipt)
    sys.exit(1)
try:
    report = json.loads(receipt.read_text())
except Exception as error:  # noqa: BLE001
    print('probe receipt unreadable:', error)
    sys.exit(1)
rows = report.get('rows', [])
print(json.dumps({'outcome': report.get('outcome'), 'passed': report.get('passed'), 'label': report.get('label'),
                  'admitted': report.get('admitted'), 'prompts': len(rows),
                  'max_mean_rel': max((x.get('mean_rel') or 0.0) for x in rows) if rows else None,
                  'max_bf16_steps': max((x.get('max_abs_in_bf16_steps') or 0.0) for x in rows) if rows else None,
                  'max_differing_fraction': max((x.get('differing_fraction') or 0.0) for x in rows) if rows else None,
                  'reasons': report.get('reasons'), 'seconds_by_bucket': report.get('seconds_by_bucket'),
                  'memory_after_probe': report.get('memory_after_probe'), 'seconds': report.get('seconds')},
                 indent=2))
if report.get('passed') is True and report.get('outcome') == 'window-qualified':
    sys.exit(0)
if report.get('outcome') in NEGATIVE:
    sys.exit(10)
print(str(report.get('error', ''))[-1500:])
sys.exit(1)
