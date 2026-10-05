#!/usr/bin/env python3
"""Packet 97 copy of run-decode-probe.py (left untouched): submit the cross-card decode probe
once and report its outcome, and require that the probe ran against the replica card(s) the
campaign asked for (`--expect-replicas xpu:2`, `xpu:1,xpu:2`, ...): the receipt's recorded
replica devices and slots, every replica's built device, and every row's per-slot hashes must
name exactly those cards, or the probe counts as not completed (exit 1, fail closed).

Exit 0: replica-exact (replica placements admitted on this server).
Exit 10: a valid negative outcome (replica-not-exact or insufficient-memory);
         the replica arm must be skipped, the server is healthy.
Exit 1: the probe did not complete or its receipt is missing/unreadable.
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
ap.add_argument('--expect-replicas', required=True, choices=('xpu:1', 'xpu:2', 'xpu:1,xpu:2', 'xpu:2,xpu:1'))
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
assert graph['440']['class_type'] == 'LTXDecodeReplicaProbe'
graph['440']['inputs']['run_name'] = a.name
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
        entry = None          # the web loop can stall while workers hold the GIL
    if entry and entry.get('status', {}).get('completed') is not None:
        if entry['status'].get('completed') or any(m[0] == 'execution_error' for m in entry['status'].get('messages', [])):
            break
    time.sleep(2)
if entry is not None:
    (req / 'history.json').write_text(json.dumps(entry, indent=2) + '\n')
receipt = run / ('decode-probe-' + a.name + '.json')
if not receipt.is_file():
    print('probe receipt missing:', receipt)
    sys.exit(1)
try:
    report = json.loads(receipt.read_text())
except Exception as error:  # noqa: BLE001
    print('probe receipt unreadable:', error)
    sys.exit(1)
rows = report.get('rows', [])


def placement_problems(report, expect):
    """Everything in the receipt that does not name exactly the expected replica card(s)."""
    want = expect.split(',')
    slots = ['replica'] + ['replica%d' % (i + 1) for i in range(1, len(want))]
    bad = []
    rec = report.get('decode_replica')
    if not isinstance(rec, dict):
        return ['receipt has no decode_replica record (not a packet 97 server?)']
    if rec.get('replica_devices') != want or rec.get('replica_slots') != slots or rec.get('decode_replicas') != len(want):
        bad.append('receipt records %r, expected %r' % (rec, want))
    if report.get('replica_device') != want[0]:
        bad.append('replica_device %r, expected %r' % (report.get('replica_device'), want[0]))
    if report.get('outcome') == 'replica-exact':
        built = {'replica': report.get('replicas') or {}}
        built.update(report.get('replica_sets') or {})
        for slot, dev in zip(slots, want):
            pair = built.get(slot) or {}
            if sorted(pair) != ['audio', 'video'] or any(r.get('device') != dev for r in pair.values()):
                bad.append('slot %s was not built on %s: %r' % (slot, dev, {k: v.get('device') for k, v in pair.items()}))
            if not isinstance(report.get(dev + '_free_after_probe'), list):
                bad.append('no free-memory reading for %s after the probe' % dev)
        for r in rows:
            for slot in slots:
                if not (isinstance(r.get(slot), dict) and r.get(slot + '_matches_reference') is True):
                    bad.append('fixture %s: slot %s not decoded or not exact' % (r.get('fixture'), slot))
    return bad


problems = placement_problems(report, a.expect_replicas)
print(json.dumps({'outcome': report.get('outcome'), 'passed': report.get('passed'),
                  'fixtures': len(rows), 'fixtures_passed': sum(1 for x in rows if x.get('passed')),
                  'expected_replicas': a.expect_replicas, 'placement_problems': problems,
                  'free_after_build': {k: v for k, v in report.items() if k.endswith('_free_after_build')},
                  'free_after_probe': {k: v for k, v in report.items() if k.endswith('_free_after_probe')},
                  'seconds': report.get('seconds')}, indent=2))
if problems:
    print('probe did not run against the requested replica card(s); refusing')
    sys.exit(1)
if report.get('passed') is True and report.get('outcome') == 'replica-exact':
    sys.exit(0)
if report.get('outcome') in ('replica-not-exact', 'insufficient-memory'):
    sys.exit(10)
print(report.get('error', '')[-1500:])
sys.exit(1)
