#!/usr/bin/env python3
"""Offline replay of one fixture prompt against a quiesced pipeline server.

Purpose: root-cause a campaign's wrong clip WITHOUT the campaign's concurrent
load. All three 2026-09-20 freezes hit under full-depth pipelined traffic, so
the heavy instrumentation path (packet 87's latent fingerprints) may only run
when the server is idle except for this one prompt.

  python scripts/replay-clip.py REPLAY-NAME \
      --graph <arm graph.json> --fixture bird \
      --server-run <run dir> \
      [--bad-output <validation dir of the failing clip>] \
      [--index-base N --index I] [--out <dir>]

Exit 0 and prints a verdict:
  MATCHES_REFERENCE   replay is bitwise the fixture reference: the wrongness
                      needs campaign concurrency (race/timing/pool alias)
  MATCHES_BAD         replay is bitwise the failing clip: deterministic wrong
                      output reproducible in isolation -> safe to fingerprint
                      this replay with the heavy (packet-87) instrumentation
  MATCHES_NEITHER     replay is a third output: nondeterministic even alone
The replay's own validation dir is left in output/validation/<name>.
"""
import argparse, json, hashlib, subprocess, sys, time, urllib.request, urllib.error
from pathlib import Path

LANE = Path(__file__).resolve().parent.parent
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
API = 'http://127.0.0.1:8188'
PY = sys.executable

ap = argparse.ArgumentParser()
ap.add_argument('name')
ap.add_argument('--graph', required=True)
ap.add_argument('--fixture', required=True)
ap.add_argument('--fixtures', default=str(LANE / 'data/stability-01-prereg.json'))
ap.add_argument('--server-run', required=True)
ap.add_argument('--bad-output', default=None, help='validation dir name of the failing clip')
ap.add_argument('--index-base', type=int, default=201088)
ap.add_argument('--index', type=int, default=0)
ap.add_argument('--out', required=True)
ap.add_argument('--timeout', type=int, default=1500)
a = ap.parse_args()

server_run = Path(a.server_run)
out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)


def call(path, payload=None, retries=30):
    assert not (ROOT / 'FAULT.json').exists(), 'device fault; halt requests'
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(API + path, data=data, headers={'Content-Type': 'application/json'})
    attempt = 0
    while True:
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.loads(r.read() or b'{}')
        except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError):
            attempt += 1
            if payload is not None or attempt > retries:
                raise
            time.sleep(10)


fixtures = {f['id']: f for f in json.loads(Path(a.fixtures).read_text())['fixtures']}
fx = fixtures[a.fixture]
fx.setdefault('reference', 'stability-01-r01-' + fx['id'])

g = json.loads(Path(a.graph).read_text())
for node in g.values():
    if 'run_name' in node.get('inputs', {}):
        node['inputs']['run_name'] = a.name
    if 'clip_index' in node.get('inputs', {}) and not isinstance(node['inputs']['clip_index'], list):
        node['inputs']['clip_index'] = a.index_base + a.index
g['364']['inputs']['text'] = fx['prompt']
g['339']['inputs']['noise_seed'] = fx['seed']
g['338']['inputs']['noise_seed'] = fx['seed']
if '75' in g:
    g['75']['inputs']['filename_prefix'] = a.name + '/preview'

queue = call('/queue')
assert not queue['queue_running'] and not queue['queue_pending'], 'server busy; replay needs a quiesced server'
assert json.loads((ROOT / 'model-verification.json').read_text())['status'] == 'passed'

req = ROOT / 'requests' / a.name
req.mkdir(parents=True, exist_ok=False)
(req / 'prompt.json').write_text(json.dumps(g, indent=2) + '\n')
r = call('/prompt', {'prompt': g, 'client_id': 'replay-' + a.name})
assert not r.get('node_errors'), r
(req / 'submission.json').write_text(json.dumps(r, indent=2) + '\n')
print('submitted %s (fixture %s, seed %d)' % (a.name, fx['id'], fx['seed']), flush=True)

deadline = time.time() + a.timeout
while time.time() < deadline:
    h = call('/history/' + r['prompt_id'])
    entry = h.get(r['prompt_id'])
    if entry:
        status = entry.get('status', {})
        for m in status.get('messages', []):
            if m[0] == 'execution_error':
                (req / 'history.json').write_text(json.dumps(entry, indent=2) + '\n')
                raise SystemExit('EXECUTION ERROR: ' + str(m[1])[:400])
        if status.get('completed'):
            (req / 'history.json').write_text(json.dumps(entry, indent=2) + '\n')
            break
    time.sleep(0.5)
else:
    raise SystemExit('TIMED OUT')


def compare(ref_name, cand_name, tag):
    parity_path = out / (a.name + '-' + tag + '.json')
    cp = subprocess.run([PY, '-B', str(LANE / 'scripts/compare-clip.py'), ref_name, cand_name,
                         '--output', str(parity_path)], capture_output=True, text=True, timeout=300)
    if not parity_path.exists():
        return {'status': 'comparator-failed', 'stderr': cp.stderr[-400:]}
    p = json.loads(parity_path.read_text())
    exact = p.get('status') == 'passed' and all(v.get('bitwise_equal') is True for v in p.get('comparisons', {}).values())
    return {'status': p.get('status'), 'bitwise_equal': exact}


time.sleep(2)  # let the validation writer finish flushing
vs_ref = compare(fx['reference'], a.name, 'vs-reference')
verdict = {'name': a.name, 'fixture': fx['id'], 'vs_reference': vs_ref}
if vs_ref['bitwise_equal']:
    verdict['verdict'] = 'MATCHES_REFERENCE'
else:
    if a.bad_output:
        vs_bad = compare(a.bad_output, a.name, 'vs-bad')
        verdict['vs_bad'] = vs_bad
        verdict['verdict'] = 'MATCHES_BAD' if vs_bad['bitwise_equal'] else 'MATCHES_NEITHER'
    else:
        verdict['verdict'] = 'NOT_REFERENCE_NO_BAD_GIVEN'
(out / (a.name + '-verdict.json')).write_text(json.dumps(verdict, indent=2) + '\n')
print(json.dumps(verdict, indent=2))
