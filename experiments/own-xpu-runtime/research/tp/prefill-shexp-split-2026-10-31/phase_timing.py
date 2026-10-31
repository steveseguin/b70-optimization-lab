#!/usr/bin/env python3
"""Per-run prefill timing of a rank-harness phase (research/tp/prefill-shexp-split-2026-10-31), CPU only, from
prefill-host-trace.jsonl (OWNRT_PREFILL_HOST_TRACE=1, extra ht): the full 256-row chunks after the first (the first carries
the cold launches), mean and median wall per chunk, inputs phase, and on rank 0 the draft chunk replay (median of the
full chunks' total from summary.json draft_replay_ms). Also the host time of the
split shared-expert sites ('shexp:*') and of the exchange sites per chunk.
Usage: phase_timing.py RUN_DIR... [--json OUT]"""
import json, statistics as st, sys
from pathlib import Path
args = sys.argv[1:]; out = None
if '--json' in args:
    i = args.index('--json'); out = args[i + 1]; del args[i:i + 2]
res = []
for run in map(Path, args):
    rk = next(run.glob('rank?'))
    rows = [json.loads(x) for x in (rk / 'prefill-host-trace.jsonl').read_text().splitlines() if x.strip()]
    full = [r for r in rows[1:] if r['rows'] == 256]
    r = dict(run=run.name, rank=int(rk.name[-1]), chunks=len(full), chunk_ms=st.mean(x['wall_ms'] for x in full),
             chunk_median_ms=st.median(x['wall_ms'] for x in full), chunk_each=[round(x['wall_ms'], 2) for x in full],
             inputs_ms=st.mean(x['inputs_ms'] for x in full),
             exchanges=st.mean(sum(v[0] for k, v in x['sites'].items() if k.startswith('exchange:')) for x in full) / 2,
             shexp_sites=st.mean(sum(v[0] for k, v in x['sites'].items() if k.startswith('shexp:')) for x in full))
    sm = json.loads((run / 'summary.json').read_text())
    if sm.get('draft_replay_ms'):
        r['draft_replay_ms_total'] = sm['draft_replay_ms']  # rank 0: all draft chunk replays of the prompt (unchanged by this lever)
    res.append(r)
    print(f"{r['run']:16s} rank {r['rank']} chunk {r['chunk_ms']:7.2f} ms (median {r['chunk_median_ms']:7.2f}; {r['chunk_each']}) inputs {r['inputs_ms']:5.2f}"
          f" exchanges/chunk {r['exchanges']:.0f} shexp sites {r['shexp_sites']:.0f}"
          + (f" draft replay total {r['draft_replay_ms_total']:.1f}" if 'draft_replay_ms_total' in r else ''))
if out:
    Path(out).write_text(json.dumps(res, indent=1) + '\n')
