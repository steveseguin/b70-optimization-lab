#!/usr/bin/env python3
"""Steady-state throughput over DISTINCT clips, with a per-clip exact-output oracle.

The earlier driver (run-throughput.py) queued the same prompt and seed for every
clip. That measures a compute rate, but the clips are identical by construction,
so the oracle cannot see a stale-conditioning or swapped-noise bug, and the
result does not demonstrate a stream of new video. This driver:

- cycles the ten stability-01 fixtures (distinct prompt AND seed) across N
  prompts, queued all at once so a pipelined encode can look the next request
  up in the server queue;
- records per-prompt evidence exactly as profile-clip.py does (prompt, identity,
  submission, history, result), so compare-clip.py can bind and compare it;
- maps every prompt to the clip it actually EMITTED (from the decode receipt's
  emitted_index when the arm pipelines, else its own index) and compares the
  emitted clip against that fixture's own pinned reference;
- measures the interval between consecutive DISTINCT emitted clips from the
  server's own execution_success timestamps; fills (a clip emitted twice) are
  listed and excluded.

No retries, no restarts. An execution error stops the driver and preserves
everything already written.
"""
import argparse, json, hashlib, subprocess, sys, time, urllib.request
from pathlib import Path

LANE = Path(__file__).resolve().parents[1]
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
API = 'http://127.0.0.1:8188'
PY = sys.executable
VIDEO_SECONDS = 25 / 24

ap = argparse.ArgumentParser()
ap.add_argument('prefix')
ap.add_argument('--graph', required=True)
ap.add_argument('--arm', required=True, help='arm name, recorded only')
ap.add_argument('--server-run', required=True)
ap.add_argument('--count', type=int, default=20)
ap.add_argument('--fixtures', default=str(LANE / 'data/stability-01-prereg.json'))
ap.add_argument('--out', required=True)
ap.add_argument('--timeout', type=int, default=1500)
a = ap.parse_args()
import re
if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,100}', a.prefix):
    raise SystemExit('prefix must be lowercase [a-z0-9-]: ' + a.prefix)
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
server_run = Path(a.server_run)


def call(path, payload=None):
    assert not (ROOT / 'FAULT.json').exists(), 'device fault; halt requests'
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(API + path, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b'{}')


fixtures = json.loads(Path(a.fixtures).read_text())['fixtures']
assert len(fixtures) == 10 and len({f['seed'] for f in fixtures}) == 10
for f in fixtures:
    f.setdefault('reference', 'stability-01-r01-' + f['id'])
    assert (ROOT / 'output/validation' / f['reference'] / 'tensors.safetensors').is_file(), f['reference']

base = json.loads(Path(a.graph).read_text())
assert base['364']['class_type'] == 'LTXPipelineTextEncode'
assert base['339']['class_type'] == 'RandomNoise' and base['338']['class_type'] == 'RandomNoise'
identity_base = json.loads((server_run / 'server-identity.json').read_text())
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip() == identity_base['boot_id']
assert json.loads((ROOT / 'model-verification.json').read_text())['status'] == 'passed'
queue = call('/queue')
assert not queue['queue_running'] and not queue['queue_pending'], 'server busy'

prompts = []
for i in range(a.count):
    fx = fixtures[i % len(fixtures)]
    name = f'{a.prefix}-{i:02d}'
    g = json.loads(json.dumps(base))
    for node in g.values():
        if 'run_name' in node.get('inputs', {}):
            node['inputs']['run_name'] = name
        if 'clip_index' in node.get('inputs', {}):
            node['inputs']['clip_index'] = i
    g['364']['inputs']['text'] = fx['prompt']
    g['339']['inputs']['noise_seed'] = fx['seed']
    g['338']['inputs']['noise_seed'] = fx['seed']
    g['75']['inputs']['filename_prefix'] = name + '/preview'
    req = ROOT / 'requests' / name
    req.mkdir(parents=True, exist_ok=False)
    (req / 'prompt.json').write_text(json.dumps(g, indent=2) + '\n')
    identity = dict(identity_base)
    identity['proc_start_ticks'] = Path(f"/proc/{identity['pid']}/stat").read_text().split(') ')[1].split()[19]
    for key, path in [('model_verification', ROOT / 'model-verification.json'),
                      ('server_args', server_run / 'server-args.json')]:
        identity[key + '_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    (req / 'identity.json').write_text(json.dumps(identity, indent=2) + '\n')
    prompts.append({'index': i, 'name': name, 'fixture': fx['id'], 'seed': fx['seed'],
                    'graph': g, 'req': req})

t_submit = time.time()
for p in prompts:
    r = call('/prompt', {'prompt': p['graph'], 'client_id': 'fixtures-' + a.prefix})
    assert not r.get('node_errors'), r
    p['prompt_id'] = r['prompt_id']
    (p['req'] / 'submission.json').write_text(json.dumps(r, indent=2) + '\n')
print('queued %d prompts (%d fixtures) in %.2f s' % (len(prompts), len(fixtures), time.time() - t_submit), flush=True)

done = 0
deadline = time.time() + a.timeout
while done < len(prompts) and time.time() < deadline:
    for p in prompts:
        if 'history' in p:
            continue
        h = call('/history/' + p['prompt_id'])
        entry = h.get(p['prompt_id'])
        if not entry:
            continue
        status = entry.get('status', {})
        for m in status.get('messages', []):
            if m[0] == 'execution_error':
                d = m[1] or {}
                print('EXECUTION ERROR in %s: %s | %s' % (p['name'], d.get('exception_type'),
                      str(d.get('exception_message'))[:400]), flush=True)
                (p['req'] / 'history.json').write_text(json.dumps(entry, indent=2) + '\n')
                raise SystemExit(2)
        if status.get('completed'):
            p['history'] = entry
            (p['req'] / 'history.json').write_text(json.dumps(entry, indent=2) + '\n')
            ts = {m[0]: m[1]['timestamp'] for m in status['messages'] if isinstance(m[1], dict) and 'timestamp' in m[1]}
            p['t_start'] = ts.get('execution_start') / 1000
            p['t_done'] = ts['execution_success'] / 1000
            (p['req'] / 'result.json').write_text(json.dumps(
                {'name': p['name'], 'prompt_id': p['prompt_id'], 'seconds': p['t_done'] - p['t_start'],
                 'status': status}, indent=2) + '\n')
            done += 1
            print('  done %s (%s) at +%.3f s' % (p['name'], p['fixture'], p['t_done'] - prompts[0]['t_start']), flush=True)
    time.sleep(0.2)
if done < len(prompts):
    print('TIMED OUT: %d/%d' % (done, len(prompts)))
    raise SystemExit(1)

# Which clip did each prompt emit? Pipelined decode arms write a receipt with emitted_index.
seen = set()
rows = []
for p in prompts:
    dec = server_run / ('pipeline-decode-' + p['name'] + '.json')
    if dec.is_file():
        emitted = json.loads(dec.read_text())['detail']['emitted_index']
    else:
        emitted = p['index']
    fx = fixtures[emitted % len(fixtures)]
    fill = emitted in seen
    seen.add(emitted)
    parity_path = out / (p['name'] + '-parity.json')
    cp = subprocess.run([PY, '-B', str(LANE / 'scripts/compare-clip.py'), fx['reference'], p['name'],
                         '--output', str(parity_path)], capture_output=True, text=True, timeout=300)
    parity = json.loads(parity_path.read_text()) if parity_path.exists() else {'status': 'missing', 'stderr': cp.stderr[-800:]}
    exact = parity.get('status') == 'passed' and all(v.get('bitwise_equal') is True for v in parity.get('comparisons', {}).values())
    rows.append({'prompt': p['name'], 'index': p['index'], 'prompt_fixture': p['fixture'],
                 'emitted_index': emitted, 'emitted_fixture': fx['id'], 'reference': fx['reference'],
                 'fill': fill, 't_done': p['t_done'], 'exact': exact, 'parity_status': parity.get('status')})
    print('  %s emitted clip %d (%s) vs %s: %s%s' % (p['name'], emitted, fx['id'], fx['reference'],
          'EXACT' if exact else 'MISMATCH ' + str(parity.get('status')), ' [fill]' if fill else ''), flush=True)

distinct = [r for r in rows if not r['fill']]
distinct.sort(key=lambda r: r['t_done'])
ivs = [round(b['t_done'] - a_['t_done'], 3) for a_, b in zip(distinct, distinct[1:])]
steady = ivs[1:] if len(ivs) > 1 else ivs
mean = sum(steady) / len(steady) if steady else None
p95 = sorted(steady)[int(round(0.95 * (len(steady) - 1)))] if steady else None
summary = {'schema': 'ltx.throughput-fixtures.v1', 'prefix': a.prefix, 'arm': a.arm,
           'graph': str(a.graph), 'server_run': str(server_run), 'count': a.count,
           'fixture_count': len(fixtures), 'distinct_clips_emitted': len(distinct),
           'fills_excluded': [r['prompt'] for r in rows if r['fill']],
           'all_exact': all(r['exact'] for r in rows),
           'intervals_between_distinct_clips_s': ivs,
           'steady_mean_s': mean, 'steady_p95_s': p95, 'steady_min_s': min(steady) if steady else None,
           'steady_max_s': max(steady) if steady else None,
           'seconds_of_wall_per_second_of_video': (mean / VIDEO_SECONDS) if mean else None,
           'effective_fps': (25 / mean) if mean else None,
           'definition': 'interval between server execution_success timestamps of consecutive distinct emitted clips; the first such interval is excluded from the mean; fills are prompts that re-emit an already-emitted clip during pipeline fill',
           'rows': rows}
(out / (a.prefix + '-throughput.json')).write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps({k: v for k, v in summary.items() if k != 'rows'}, indent=2))
if not summary['all_exact']:
    raise SystemExit(3)
