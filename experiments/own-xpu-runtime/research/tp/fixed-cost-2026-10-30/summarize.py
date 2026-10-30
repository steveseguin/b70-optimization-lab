#!/usr/bin/env python3
"""Per-step harness savings of research/tp/fixed-cost-2026-10-30 (CPU only): reads results/f*-timing.json (analyze.py
timing output: medians of halves 3..64 per arm) and writes results/steps.json with A/B means per step and rank."""
import json, statistics as st
from pathlib import Path
R = Path(__file__).resolve().parent / 'results'
def arms(f): return {x['run']: x for x in json.loads((R / f).read_text())}
def m(d, names): v = [d[n]['half_ms'] for n in names if n in d]; return round(st.fmean(v), 4) if v else None
out = {}
a = arms('f1-rank1-timing.json'); out['F1 rank 1'] = dict(off=m(a, ['g1-r1-full', 'g1-r1-full2']), on=m(a, ['g1-r1-full-ep', 'g1-r1-full-ep2']), one_off=m(a, ['g1-r1-one']), one_on=m(a, ['g1-r1-one-ep']))
a = arms('f1-rank0-timing.json'); out['F1 rank 0'] = dict(off=m(a, ['g2-r0-full', 'g2-r0-full2']), on=m(a, ['g2-r0-full-ep', 'g2-r0-full-ep2']), one_off=m(a, ['g2-r0-one']), one_on=m(a, ['g2-r0-one-ep']))
a = arms('f2-rank1-timing.json'); out['F2 rank 1'] = dict(off=m(a, ['g3-r1-full-ep', 'g3-r1-full-ep2']), on=m(a, ['g3-r1-full-ep-rd', 'g3-r1-full-ep-rd2', 'g3b-r1-full-ep-rd']), one_off=m(a, ['g3-r1-one']), one_on=m(a, ['g3-r1-one-rd']))
a = arms('f2-rank0-timing.json'); out['F2 rank 0'] = dict(off=m(a, ['g4-r0-full-ep', 'g4-r0-full-ep2']), on=m(a, ['g4-r0-full-ep-rd', 'g4-r0-full-ep-rd2']), one_off=m(a, ['g4-r0-one']), one_on=m(a, ['g4-r0-one-rd']))
a = arms('f3a-gdn-prep0-timing.json'); out['F3a rank 1'] = dict(off=m(a, ['g5-r1-full-epr', 'g5-r1-full-epr2']), on=m(a, ['g5-r1-full-epr-gp0', 'g5-r1-full-epr-gp02']))
out['F3a rank 0'] = dict(off=m(a, ['g5-r0-full-epr', 'g5-r0-full-epr2']), on=m(a, ['g5-r0-full-epr-gp0', 'g5-r0-full-epr-gp02']))
for k, v in out.items():
    v['saving_ms'] = round(v['off'] - v['on'], 4)
    if v.get('one_off'): v['one_card_saving_ms'] = round(v['one_off'] - v['one_on'], 4)
    print(k, v)
(R / 'steps.json').write_text(json.dumps(out, indent=1) + '\n')
