#!/usr/bin/env python3
"""Packet 94: submit the capture-freeze / memory-floor admission once.

Exit 0: frozen (every card at or above 2 GiB free; timed arms replay only).
Exit 10: refused (memory floor or busy pipeline); skip the timed arm, server healthy.
Exit 1: no receipt. No retries.
"""
import argparse, json, re, sys, time, urllib.error, urllib.request
from pathlib import Path

ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
API = 'http://127.0.0.1:8188'
ap = argparse.ArgumentParser()
ap.add_argument('name')
ap.add_argument('--graph', required=True)
ap.add_argument('--server-run', required=True)
ap.add_argument('--timeout', type=int, default=300)
a = ap.parse_args()
if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,100}', a.name):
    raise SystemExit('name must be lowercase [a-z0-9-]')


def call(path, payload=None):
    assert not (ROOT / 'FAULT.json').exists(), 'device fault; halt requests'
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(API + path, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b'{}')


graph = json.loads(Path(a.graph).read_text())
assert graph['480']['class_type'] == 'LTXSamplerCaptureFreeze'
graph['480']['inputs']['run_name'] = a.name
q = call('/queue')
assert not q['queue_running'] and not q['queue_pending'], 'server busy'
req = ROOT / 'requests' / a.name
req.mkdir(parents=True, exist_ok=False)
(req / 'prompt.json').write_text(json.dumps(graph, indent=2) + '\n')
r = call('/prompt', {'prompt': graph, 'client_id': 'freeze-' + a.name})
assert not r.get('node_errors'), r
(req / 'submission.json').write_text(json.dumps(r, indent=2) + '\n')
receipt = Path(a.server_run) / ('sampler-capture-freeze-' + a.name + '.json')
deadline = time.time() + a.timeout
while time.time() < deadline and not receipt.is_file():
    time.sleep(1)
if not receipt.is_file():
    print('freeze receipt missing:', receipt)
    sys.exit(1)
time.sleep(1)
rep = json.loads(receipt.read_text())
print(json.dumps({k: rep.get(k) for k in ('outcome', 'frozen', 'free_gib', 'reserved_gib', 'placement')}, indent=1))
sys.exit(0 if rep.get('frozen') and rep.get('outcome') == 'frozen' else 10)
