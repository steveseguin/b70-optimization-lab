#!/usr/bin/env python3
"""Harness timing summary of research/tp/prefill-host-2026-10-30 (copy of prefill-speed-2026-10-29's; adds the median full
chunk, which the one-off 1 s host stall of g1-r1-new's second chunk does not move, and the draft chunk's host split) from the compact evidence (CPU only): per configuration the
mean of the full 256-row chunks after the first (host trace) and the rank-0 draft replay per 256 rows. Writes
results/harness-timing.json."""
import json, statistics as st
from pathlib import Path
D = Path(__file__).resolve().parent; E = D / 'evidence'
def chunks(run, rank):
    rows = [json.loads(l) for l in (E / run / 'prefill-host-trace.jsonl').read_text().splitlines()]
    full = [r for r in rows[1:] if r['rows'] == 256]
    m = lambda k: st.mean(r[k] for r in full)
    act = st.mean(r['wall_ms'] - r['inputs_blocked_ms'] - r['loop_blocked_ms'] - r['final_blocked_ms'] for r in full)
    sites = {}
    for r in full:
        for k, (n, h, b) in r['sites'].items():
            s = sites.setdefault(k, [0, 0., 0.]); s[0] += n / len(full); s[1] += h / len(full); s[2] += b / len(full)
    top = sorted(((k, round(v[1] - v[2], 2)) for k, v in sites.items()), key=lambda x: -x[1])[:6]
    return dict(chunks=len(full), wall_ms=m('wall_ms'), wall_ms_median=st.median(r['wall_ms'] for r in full), wall_ms_each=[round(r['wall_ms'], 1) for r in full], inputs_ms=m('inputs_ms'), loop_ms=m('loop_ms'), loop_blocked_ms=m('loop_blocked_ms'),
                host_active_ms=act, host_waits=m('host_waits'), submissions_per_card=[st.mean(r['submitted'][c] for r in full) for c in (0, 1)],
                exchange_sites=sum(v[0] for k, v in sites.items() if k.startswith('exchange:')), top_host_active_ms=top)
def draft(run):
    s = json.loads((E / run / 'summary.json').read_text())
    p = E / run / 'draft-chunk-replays.jsonl'
    if p.exists() and p.stat().st_size:
        c = [json.loads(l)['chunk_replay'] for l in p.read_text().splitlines()]
        full = [x for x in c if x['rows'] == 256][1:]
        return dict(mode='chunk' + ('+kv_only' if full[0].get('kv_only') else ''), per_256_rows_ms=st.mean(x['wall_ms'] for x in full),
                    staged_ms=st.mean(x['staged_ms'] for x in full), replay_ms_1099_rows=s['draft_replay_ms'],
                    **{k: st.mean(x[k] for x in full) for k in ('sites_ms', 'admit_ms', 'copy_ms', 'guard_ms', 'stage_wait_ms') if k in full[0]},
                    **{k: full[0][k] for k in ('stage_thread', 'guard_row', 'row_copy', 'guards', 'commands') if k in full[0]})
    t = [json.loads(l) for l in (E / run / 'draft-host-trace.jsonl').read_text().splitlines() if '"head":false' in l]
    return dict(mode='per-row', per_256_rows_ms=256 * st.median(x['wall_ms'] for x in t), row_inputs_ms=st.median(x['inputs_ms'] for x in t),
                row_issue_ms=st.median(x['issue_ms'] for x in t), row_blocked_ms=st.median(x['blocked_ms'] for x in t), replay_ms_1099_rows=s['draft_replay_ms'])
out = {
 'rank0': {'tptsxqckf (g1, 2bca4e65084d)': dict(prefill=chunks('g1/g1-r0-off', 0), draft=draft('g1/g1-r0-off')),
           'tptsxqckf + sr lt=4 st gr (g1, 2bca4e65084d)': dict(prefill=chunks('g1/g1-r0-new', 0), draft=draft('g1/g1-r0-new')),
           'tptsxqckf (g2, c8e173bf4e7d)': dict(prefill=chunks('g2/g2-r0-off', 0), draft=draft('g2/g2-r0-off')),
           'tptsxqckf + sr lt=4 st gr rc (g2, c8e173bf4e7d)': dict(prefill=chunks('g2/g2-r0-c', 0), draft=draft('g2/g2-r0-c'))},
 'rank1': {'tptsxqckf (g1, 2bca4e65084d)': dict(prefill=chunks('g1/g1-r1-off', 1)),
           'tptsxqckf + sr (g1, 2bca4e65084d)': dict(prefill=chunks('g1/g1-r1-new', 1))}}
(D / 'results/harness-timing.json').write_text(json.dumps(out, indent=1) + '\n')
for rank, cfgs in out.items():
    for k, v in cfgs.items():
        p = v['prefill']; d = v.get('draft')
        print(f"{rank} {k}: chunk {p['wall_ms']:.1f} ms (median {p['wall_ms_median']:.1f}, each {p['wall_ms_each']}; inputs {p['inputs_ms']:.1f}, loop {p['loop_ms']:.1f}, blocked {p['loop_blocked_ms']:.1f}, host-active {p['host_active_ms']:.1f}, subm/card {p['submissions_per_card'][0]:.0f}, exch sites {p['exchange_sites']:.0f})"
              + (f"; draft {d['mode']} {d['per_256_rows_ms']:.1f} ms/256 rows" if d else ''))
