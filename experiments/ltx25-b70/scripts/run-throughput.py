#!/usr/bin/env python3
"""Steady-state throughput, which is what the goal actually asks for.

Everything in this lane so far measures single-clip LATENCY. The goal is
"one second of new video in under one second, continuously", i.e. the interval
between finished clips when they are produced back to back. This queues N
prompts at once and measures that interval.
"""
import argparse, json, time, urllib.request
from pathlib import Path

ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
API = 'http://127.0.0.1:8188'

ap = argparse.ArgumentParser()
ap.add_argument('prefix')
ap.add_argument('--graph', required=True)
ap.add_argument('--mode', required=True)
ap.add_argument('--count', type=int, default=6)
ap.add_argument('--out', required=True)
a = ap.parse_args()
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)

# The gates accept only lowercase run names ([a-z0-9][a-z0-9-]{0,119}). A single
# uppercase letter in the prefix made every prompt fail with "Unsafe request
# name", tripped a gate's sticky-failure latch, and -- because the poll loop
# below only ever looked for completion -- hung for ten minutes instead of
# saying so. Check it here, and check for execution errors there.
import re as _re
if not _re.fullmatch(r'[a-z0-9][a-z0-9-]{0,110}', a.prefix):
    raise SystemExit('prefix must match [a-z0-9][a-z0-9-]* (lowercase): ' + a.prefix)


def call(path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(API + path, data=data,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b'{}')


base = json.loads(Path(a.graph).read_text())
assert base['422']['inputs']['mode'] == a.mode

ids = []
t_submit = time.time()
for i in range(a.count):
    name = f'{a.prefix}-{i:02d}'
    g = json.loads(json.dumps(base))
    for node in g.values():
        if 'run_name' in node.get('inputs', {}):
            node['inputs']['run_name'] = name
        # Encode-ahead keys its jobs on the clip index, so a stream has to
        # advance it; leaving every clip at 0 would make clip 1 collect a value
        # queued for clip 0 and stall.
        if 'clip_index' in node.get('inputs', {}):
            node['inputs']['clip_index'] = i
    g['75']['inputs']['filename_prefix'] = name + '/preview'
    r = call('/prompt', {'prompt': g, 'client_id': 'throughput-' + a.prefix})
    ids.append((name, r['prompt_id']))
print('queued %d prompts in %.2f s' % (len(ids), time.time() - t_submit))

done = {}
deadline = time.time() + 900
while len(done) < len(ids) and time.time() < deadline:
    for name, pid in ids:
        if pid in done:
            continue
        h = call('/history/' + pid)
        entry = h.get(pid)
        if not entry:
            continue
        status = entry.get('status', {})
        # Fail fast. A prompt that errored will never report completed, and
        # several gates latch sticky on failure, so every later prompt fails
        # too; polling on would just burn the clock.
        for message in status.get('messages', []):
            if message[0] == 'execution_error':
                detail = message[1] or {}
                print('EXECUTION ERROR in %s: %s | %s' % (
                    name, detail.get('exception_type'),
                    str(detail.get('exception_message'))[:300]))
                raise SystemExit(2)
        if status.get('status_str') == 'error':
            print('PROMPT %s reported status error' % name)
            raise SystemExit(2)
        if status.get('completed'):
            done[pid] = (name, time.time())
    time.sleep(0.25)

if len(done) < len(ids):
    print('TIMED OUT: %d/%d finished' % (len(done), len(ids)))
    raise SystemExit(1)

order = sorted(done.values(), key=lambda z: z[1])
t0 = order[0][1]
print('\n%-16s %10s %12s' % ('clip', 'finished', 'interval'))
intervals = []
for i, (name, t) in enumerate(order):
    iv = None if i == 0 else t - order[i - 1][1]
    if iv is not None:
        intervals.append(iv)
    print('%-16s %9.3f s %11s' % (name, t - t0, ('%.3f s' % iv) if iv else '-'))

warm = intervals[1:] if len(intervals) > 1 else intervals
mean = sum(warm) / len(warm)
print('\nsteady-state interval: mean %.3f s  min %.3f s  max %.3f s  (%d warm clips)'
      % (mean, min(warm), max(warm), len(warm)))
print('video produced per clip: 1.042 s (25 frames @ 24 fps)')
print('=> %.2f s of compute per second of video   (goal: < 1.00)' % (mean / 1.042))
(out / (a.prefix + '-throughput.json')).write_text(json.dumps(
    {'prefix': a.prefix, 'mode': a.mode, 'count': a.count,
     'intervals_s': intervals, 'mean_warm_interval_s': mean,
     'seconds_of_compute_per_second_of_video': mean / 1.042}, indent=2) + '\n')
