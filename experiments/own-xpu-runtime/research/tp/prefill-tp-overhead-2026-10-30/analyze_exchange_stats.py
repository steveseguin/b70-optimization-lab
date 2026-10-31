#!/usr/bin/env python3
"""Per-exchange statistics of TP batched prefill (research/tp/prefill-tp-overhead-2026-10-30), CPU only.
Input: a TP rank harness run with OWNRT_TP_EXCHANGE_STATS=0 (RUN/rank<r>/tp-exchange-sites.json, tp-exchange-slots.json).
The exchange kernel's waiting work-item records, per site and card, 'own' cycles (kernel entry to the start of its wait:
its stores into the peer, fences, barrier, counter and flag) and 'wait' cycles (polling for the peer's flag), on the EU
thread clock (2.80 cycles/ns, research/tp/stage-overhead-2026-10-30). Batched prefill uses slot = decode slot + 128 and
zeroes those records before every chunk, so they hold the LAST chunk's values (one execution per site): run a prompt that
is a multiple of the chunk rows so the last chunk is full.
Usage: analyze_exchange_stats.py RUN RANK [--json OUT]"""
import json, sys, collections
from pathlib import Path
run, rank = Path(sys.argv[1]), sys.argv[2]
out_path = sys.argv[sys.argv.index('--json') + 1] if '--json' in sys.argv else None
d = run / f'rank{rank}'
sites = json.loads((d / 'tp-exchange-sites.json').read_text())
slots = {s['slot']: s for s in json.loads((d / 'tp-exchange-slots.json').read_text())['slots']}
CYC_PER_MS = 2.80e6
rows = []
for c, recs in enumerate(sites['cards']):
    for r in recs:
        if r['slot'] < 128: continue  # decode slots
        s = slots.get(r['slot'] - 128, {})
        rows.append(dict(card=c, slot=r['slot'], label=s.get('label'), op=s.get('op'), values=s.get('values'), n=r['n'],
                         own_ms=r['own_cycles'] / max(1, r['n']) / CYC_PER_MS, wait_ms=r['wait_cycles'] / max(1, r['n']) / CYC_PER_MS))
def kind(label):
    if not label: return '?'
    if label.endswith('tp_xcompact'): return 'experts (compact slots)'
    if label.endswith('qsa.attention.tp_xgather'): return 'qsa attention'
    if label.endswith('attention.tp_xgather'): return 'attention out-proj'
    if label.endswith('tp_xheads'): return 'gdn gated'
    return label
summary = collections.defaultdict(lambda: dict(sites=0, own_ms=[0.0, 0.0], wait_ms=[0.0, 0.0]))
for r in rows:
    k = summary[kind(r['label'])]; k['own_ms'][r['card']] += r['own_ms']; k['wait_ms'][r['card']] += r['wait_ms']
    if r['card'] == 0: k['sites'] += 1
tot = dict(own_ms=[sum(r['own_ms'] for r in rows if r['card'] == c) for c in (0, 1)], wait_ms=[sum(r['wait_ms'] for r in rows if r['card'] == c) for c in (0, 1)])
res = dict(run=str(run), rank=int(rank), per_chunk_totals=tot, by_kind=summary, sites=rows)
if out_path: Path(out_path).write_text(json.dumps(res, indent=1) + '\n')
print(f"rank {rank} last chunk: exchange own ms card0/card1 {tot['own_ms'][0]:.1f}/{tot['own_ms'][1]:.1f}, wait ms {tot['wait_ms'][0]:.1f}/{tot['wait_ms'][1]:.1f}")
for k, v in summary.items():
    print(f"  {k:26s} sites {v['sites']:3d}  own {v['own_ms'][0]:6.2f}/{v['own_ms'][1]:6.2f}  wait {v['wait_ms'][0]:6.2f}/{v['wait_ms'][1]:6.2f}")
