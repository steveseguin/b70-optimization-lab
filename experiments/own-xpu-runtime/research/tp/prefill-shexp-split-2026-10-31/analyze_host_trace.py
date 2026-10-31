#!/usr/bin/env python3
"""CPU analysis of OWNRT_PREFILL_HOST_TRACE=1 output (research/tp/prefill-speed-2026-10-29).
prefill-host-trace.jsonl: one line per prefill chunk (host time of the submitting thread, time blocked on the cards in
Engine::wait, drains, submissions per card, per site class {count, host ms, blocked ms}); draft-host-trace.jsonl: one
line per synchronous draft row (inputs, issue, wall, blocked). Usage: analyze_host_trace.py RUN_DIR [RANK] [--json OUT]"""
import json, sys, statistics as st
from pathlib import Path
run = Path(sys.argv[1]); rank = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else ('0' if (run / 'rank0').exists() else '1')
out = sys.argv[sys.argv.index('--json') + 1] if '--json' in sys.argv else None
d = run / f'rank{rank}'
rows = [json.loads(l) for l in (d / 'prefill-host-trace.jsonl').read_text().splitlines()]
res = dict(run=str(run), rank=int(rank), chunks=[])
for r in rows:
    host_active = r['wall_ms'] - r['inputs_blocked_ms'] - r['loop_blocked_ms'] - r['final_blocked_ms']
    cls = {}
    for k, (n, h, b) in r['sites'].items():
        kind = k.split(':')[0]
        c = cls.setdefault(kind, [0, 0.0, 0.0]); c[0] += n; c[1] += h; c[2] += b
    res['chunks'].append(dict(position=r['position'], rows=r['rows'], wall_ms=r['wall_ms'], inputs_ms=r['inputs_ms'], loop_ms=r['loop_ms'],
                              loop_blocked_ms=r['loop_blocked_ms'], final_ms=r['final_ms'], final_blocked_ms=r['final_blocked_ms'],
                              host_active_ms=host_active, host_waits=r['host_waits'], submitted=r['submitted'], classes=cls, sites=r['sites']))
for c in res['chunks']:
    print(f"pos {c['position']:5d} rows {c['rows']:3d} wall {c['wall_ms']:7.1f}  inputs {c['inputs_ms']:6.1f}  loop {c['loop_ms']:6.1f} (blocked {c['loop_blocked_ms']:6.1f})"
          f"  final {c['final_ms']:5.1f} (blocked {c['final_blocked_ms']:5.1f})  host-active {c['host_active_ms']:6.1f}  waits {c['host_waits']} subm {c['submitted']}")
full = [c for c in res['chunks'][1:] if c['rows'] == max(x['rows'] for x in res['chunks'])]
if full:
    print('\nfull chunks after the first (%d): per site class, mean per chunk: count / host ms / blocked ms' % len(full))
    keys = sorted({k for c in full for k in c['sites']})
    agg = {}
    for k in keys:
        n = st.mean(c['sites'].get(k, [0, 0, 0])[0] for c in full); h = st.mean(c['sites'].get(k, [0, 0, 0])[1] for c in full); b = st.mean(c['sites'].get(k, [0, 0, 0])[2] for c in full)
        agg[k] = [n, h, b]
    for k, (n, h, b) in sorted(agg.items(), key=lambda x: -x[1][1]):
        print(f'  {k:34s} {n:7.0f} {h:8.2f} {b:8.2f}  host-active {h-b:7.2f}')
    res['full_chunk_mean'] = dict(wall_ms=st.mean(c['wall_ms'] for c in full), inputs_ms=st.mean(c['inputs_ms'] for c in full),
                                  loop_ms=st.mean(c['loop_ms'] for c in full), loop_blocked_ms=st.mean(c['loop_blocked_ms'] for c in full),
                                  final_ms=st.mean(c['final_ms'] for c in full), final_blocked_ms=st.mean(c['final_blocked_ms'] for c in full),
                                  host_active_ms=st.mean(c['host_active_ms'] for c in full), sites=agg)
    print('mean full chunk:', {k: round(v, 2) for k, v in res['full_chunk_mean'].items() if k != 'sites'})
dt = d / 'draft-host-trace.jsonl'
if dt.exists():
    dr = [json.loads(l) for l in dt.read_text().splitlines()]
    pr = [x for x in dr if not x['head']]
    if pr:
        m = lambda k: st.median(x[k] for x in pr)
        res['draft_rows'] = dict(rows=len(pr), inputs_ms=m('inputs_ms'), issue_ms=m('issue_ms'), wall_ms=m('wall_ms'), blocked_ms=m('blocked_ms'),
                                 sum_wall_ms=sum(x['wall_ms'] for x in pr))
        print('\ndraft prompt rows (median ms):', {k: round(v, 4) for k, v in res['draft_rows'].items()})
if out:
    Path(out).write_text(json.dumps(res, indent=1) + '\n')
