#!/usr/bin/env python3
"""Submit packet 92a's switch-interval knob once and report its outcome.

Exit 0: applied. Exit 10: refused (the pipeline stayed busy; the receipt says
why). Exit 1: the request did not complete or its receipt is missing.
No retries. Writes prompt/submission/history under R/requests/<name>/.
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

ap = argparse.ArgumentParser()
ap.add_argument('name')
ap.add_argument('--graph', required=True)
ap.add_argument('--server-run', required=True)
ap.add_argument('--timeout', type=int, default=300)
ap.add_argument('--ms', type=float, required=True)
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
assert graph['450']['class_type'] == 'LTXSchedulerKnob'
graph['450']['inputs']['run_name'] = a.name
graph['450']['inputs']['switch_interval_ms'] = a.ms
queue = call('/queue')
assert not queue['queue_running'] and not queue['queue_pending'], 'server busy'
req = ROOT / 'requests' / a.name
req.mkdir(parents=True, exist_ok=False)
(req / 'prompt.json').write_text(json.dumps(graph, indent=2) + '\n')
r = call('/prompt', {'prompt': graph, 'client_id': 'knob-' + a.name})
assert not r.get('node_errors'), r
(req / 'submission.json').write_text(json.dumps(r, indent=2) + '\n')
deadline = time.time() + a.timeout
entry = None
while time.time() < deadline:
    try:
        entry = call('/history/' + r['prompt_id']).get(r['prompt_id'])
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        entry = None          # the web loop can stall while workers hold the GIL
    if entry and entry.get('status', {}).get('completed') is not None:
        if entry['status'].get('completed') or any(m[0] == 'execution_error' for m in entry['status'].get('messages', [])):
            break
    time.sleep(2)
if entry is not None:
    (req / 'history.json').write_text(json.dumps(entry, indent=2) + '\n')
receipt = run / ('scheduler-knob-' + a.name + '.json')
if not receipt.is_file():
    print('knob receipt missing:', receipt)
    sys.exit(1)
try:
    report = json.loads(receipt.read_text())
except Exception as error:  # noqa: BLE001
    print('knob receipt unreadable:', error)
    sys.exit(1)
knob = report.get('knob', {})
lag = report.get('gil', {}).get('lag', {})
print(json.dumps({'requested_ms': a.ms, 'applied': knob.get('applied'), 'now_s': knob.get('now_s'),
                  'reason': knob.get('reason'), 'lag_samples': lag.get('samples')}, indent=2))
sys.exit(0 if knob.get('applied') is True else 10)
