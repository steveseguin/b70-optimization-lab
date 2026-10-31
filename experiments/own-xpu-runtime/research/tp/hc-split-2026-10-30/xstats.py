#!/usr/bin/env python3
"""Per-class exchange statistics of OWNRT_TP_EXCHANGE_STATS runs (hc-split-2026-10-30): own time (stores, fences,
counter, flag) and wait of each exchange site, per card, from rank<r>/tp-exchange-sites.json + tp-exchange-slots.json
(sub-group clock cycles, 2.80 cycles/ns as measured in research/tp/stage-overhead-2026-10-30). Per class: sites, mean us
per execution of own time and wait on each card, and the total per half (executions / halves).
Usage: xstats.py RUN [RUN...]   prints one block per run; writes nothing."""
import json, sys
from collections import defaultdict
from pathlib import Path
CYC = 2.80e3  # cycles per us
for run in sys.argv[1:]:
    r = next(Path(run).glob('rank*/tp-exchange-sites.json')).parent
    labels = {s['slot']: s['label'] for s in json.loads((r / 'tp-exchange-slots.json').read_text())['slots']}
    cards = json.loads((r / 'tp-exchange-sites.json').read_text())['cards']
    agg = defaultdict(lambda: [0, 0, [0.0, 0.0], [0.0, 0.0]])  # sites, executions, own us, wait us per card
    for c, recs in enumerate(cards):
        for x in recs:
            lab = labels[x['slot']]
            cls = lab.split('.', 2)[2] if lab.startswith('blk.') else lab
            cls = cls.replace('.tp_xgather', '').replace('.tp_xheads', '').replace('.tp_xcompact', '')
            a = agg[cls]
            if c == 0: a[0] += 1; a[1] += x['n']
            a[2][c] += x['own_cycles'] / CYC; a[3][c] += x['wait_cycles'] / CYC
    halves = max(1, max(x['n'] for x in cards[0]) )
    print(f'== {run}: {len(labels)} exchange slots; executions per slot up to {halves}')
    tot = [0.0, 0.0, 0.0, 0.0]
    for cls, (sites, n, own, wait) in sorted(agg.items(), key=lambda kv: -kv[1][0]):
        per = lambda v: v / n if n else 0
        print(f'  {cls:28s} sites {sites:3d}  own us {per(own[0]):5.2f} / {per(own[1]):5.2f}  wait us {per(wait[0]):5.2f} / {per(wait[1]):5.2f}'
              f'  per half own {own[0]/halves*1e-3:6.3f} / {own[1]/halves*1e-3:6.3f} ms  wait {wait[0]/halves*1e-3:6.3f} / {wait[1]/halves*1e-3:6.3f} ms')
        tot = [tot[0] + own[0], tot[1] + own[1], tot[2] + wait[0], tot[3] + wait[1]]
    print(f'  total per half: own {tot[0]/halves*1e-3:.3f} / {tot[1]/halves*1e-3:.3f} ms, wait {tot[2]/halves*1e-3:.3f} / {tot[3]/halves*1e-3:.3f} ms')
