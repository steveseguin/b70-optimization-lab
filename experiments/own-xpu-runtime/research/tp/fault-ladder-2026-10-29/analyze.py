#!/usr/bin/env python3
"""Rank-0 harness timing of research/tp/rank0-trims-2026-10-29: per run, medians over decode steps 3.. of the driver's
wall times (half: the HALF call that delivers each position: the speculative half for hits, the redo for misses; spec:
every speculative HALF; rollback; redo; draft) and of rank 0's own p150 host segments in the decode region
(snapshot, token_prep, layer_body, half_total, rollback; only the native controller flushes them) and of its per-half
rows (half_completion_ms, prepare_ms, enqueue_loop_ms, wait_ms; speculative and confirmed halves). Usage: analyze.py OUT.json RUN_DIR..."""
import json, statistics as st, sys
from pathlib import Path
def med(v): return round(st.median(v), 4) if v else None
out = {}
for run in sys.argv[2:]:
    r = Path(run); s = json.loads((r / 'summary.json').read_text()); first = s['prompt']
    seg, rows = {}, {}
    for line in open(r / 'rank0/timings.jsonl'):
        x = json.loads(line)
        if 'p150_segment' in x and x['position'] >= first + 2: seg.setdefault(x['p150_segment'], []).append(x['ms'])
        elif 'half_completion_ms' in x and x['position'] >= first + 2 and not x['cancelled']:
            kind = 'speculative' if x['speculative'] else 'confirmed'
            for f in ('half_completion_ms', 'prepare_ms', 'enqueue_loop_ms', 'wait_ms'): rows.setdefault(kind + '.' + f, []).append(x[f])
    k = lambda v: v[2:] if len(v) > 4 else v
    hd = [h + d for h, d in zip(s['half_ms'][2:], s['draft_ms'][2:])]
    out[r.name] = dict(pattern=s['pattern'], steps=s['steps'], events=s['events'], env={kk: vv for kk, vv in s['tp_env'].items() if not kk.startswith('OWNRT_TP_')},
                       half=med(k(s['half_ms'])), draft=med(k(s['draft_ms'])), half_plus_draft=med(hd),
                       spec=med(k(s.get('spec_ms', []))), rollback=med(k(s.get('rollback_ms', []))), redo=med(k(s.get('redo_ms', []))),
                       p150={n: med(v) for n, v in sorted(seg.items())}, p150_n={n: len(v) for n, v in sorted(seg.items())},
                       rank_rows={n: med(v) for n, v in sorted(rows.items())}, rank_rows_n={n: len(v) for n, v in sorted(rows.items())})
    print(r.name, json.dumps({kk: out[r.name][kk] for kk in ('half', 'draft', 'half_plus_draft', 'spec', 'rollback', 'redo')}), json.dumps(out[r.name]['rank_rows']))
Path(sys.argv[1]).write_text(json.dumps(out, indent=1) + '\n')
