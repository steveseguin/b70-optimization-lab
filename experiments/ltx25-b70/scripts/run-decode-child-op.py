#!/usr/bin/env python3
"""Submit one packet-92b decode-child request (probe or stop) and report it.

  --op probe: exit 0 child-exact (child arm admitted); 10 a valid negative
              outcome (child-not-exact, insufficient-memory, child-unavailable;
              the child has been stopped); 1 incomplete or error.
  --op stop:  exit 0 the child process exited; 1 it did not (never killed).
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
ap.add_argument('--timeout', type=int, default=1200)
ap.add_argument('--op', choices=('probe', 'stop'), required=True)
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
NODES = {'probe': ('460', 'LTXDecodeChildProbe', 'decode-child-probe-'),
         'stop': ('461', 'LTXDecodeChildStop', 'decode-child-stop-')}
node_id, cls, receipt_prefix = NODES[a.op]
assert graph[node_id]['class_type'] == cls
graph[node_id]['inputs']['run_name'] = a.name
queue = call('/queue')
assert not queue['queue_running'] and not queue['queue_pending'], 'server busy'
req = ROOT / 'requests' / a.name
req.mkdir(parents=True, exist_ok=False)
(req / 'prompt.json').write_text(json.dumps(graph, indent=2) + '\n')
r = call('/prompt', {'prompt': graph, 'client_id': 'child-' + a.name})
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
receipt = run / (receipt_prefix + a.name + '.json')
if not receipt.is_file():
    print('receipt missing:', receipt)
    sys.exit(1)
try:
    report = json.loads(receipt.read_text())
except Exception as error:  # noqa: BLE001
    print('receipt unreadable:', error)
    sys.exit(1)
if a.op == 'stop':
    print(json.dumps({'exited': report.get('exited'), 'returncode': report.get('returncode'),
                      'reason': report.get('reason') or report.get('error'),
                      'xpu3_free_after': report.get('xpu3_free_after')}, indent=2))
    sys.exit(0 if report.get('exited') is True else 1)
rows = report.get('rows', [])
print(json.dumps({'outcome': report.get('outcome'), 'passed': report.get('passed'),
                  'fixtures': len(rows), 'fixtures_passed': sum(1 for x in rows if x.get('passed')),
                  'xpu3_free_after_child_load': report.get('xpu3_free_after_child_load'),
                  'xpu3_free_after_probe': report.get('xpu3_free_after_probe'),
                  'child_stop': report.get('child_stop'), 'seconds': report.get('seconds')}, indent=2))
if report.get('passed') is True and report.get('outcome') == 'child-exact':
    sys.exit(0)
if report.get('outcome') in ('child-not-exact', 'insufficient-memory', 'child-unavailable'):
    sys.exit(10)
print(str(report.get('error', ''))[-1500:])
sys.exit(1)
