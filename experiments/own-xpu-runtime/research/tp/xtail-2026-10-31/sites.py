#!/usr/bin/env python3
"""Per-site device times from OWNRT_SITE_TRACE runs (rank<r>/site-trace.jsonl, one card only), fixed-cost-2-2026-10-30.
Usage: sites.py RUNS_DIR OUT.json ARM_A ARM_B [KIND]   KIND: draft_head (default) or half (labels summed per site type,
the blk.<n>. prefix dropped).
For each arm: per launch index of the phase (median over phases after the first 8), its class label, device us, and the
summed device time of the phase; then per class label A vs B. Device time only (profiler timestamps), not wall time."""
import json, statistics as st, sys
from collections import defaultdict
from pathlib import Path


def load(run, kind):
    run = Path(run)
    trace = next(run.glob('rank*/site-trace.jsonl'))
    kinds, rows = {}, defaultdict(list)
    for line in open(trace):
        d = json.loads(line)
        if 'phase' in d:
            kinds[d['phase']] = d['kind']
            continue
        if kinds.get(d['p']) == kind:
            rows[d['p']].append(d)
    phases = sorted(rows)[8:]
    n = st.mode(len(rows[p]) for p in phases)
    phases = [p for p in phases if len(rows[p]) == n]
    per = defaultdict(list)
    spans, busy = [], []
    for p in phases:
        r = rows[p]
        for i, d in enumerate(r):
            per[i].append((d['e'] - d['s']) / 1000)
        spans.append((r[-1]['e'] - r[0]['s']) / 1000)
        busy.append(sum((d['e'] - d['s']) for d in r) / 1000)
    labels = [d['c'] for d in rows[phases[0]]]
    launches = [dict(i=i, site=labels[i], us=round(st.median(per[i]), 3)) for i in range(n)]
    by = defaultdict(float)
    for x in launches:
        site = x['site']
        if kind == 'half' and site.startswith('blk.'):
            site = site.split('.', 2)[2]
        by[site] += x['us']
    return dict(trace=str(trace), phases=len(phases), launches=n, span_us=round(st.median(spans), 2),
                busy_us=round(st.median(busy), 2), launch_list=launches, by_site={k: round(v, 3) for k, v in by.items()})


def main():
    runs, out, a, b = sys.argv[1:5]
    kind = sys.argv[5] if len(sys.argv) > 5 else 'draft_head'
    A, B = load(Path(runs) / a, kind), load(Path(runs) / b, kind)
    print(f'{kind}: {a} span {A["span_us"]} busy {A["busy_us"]} us in {A["launches"]} launches ({A["phases"]} phases)')
    print(f'{kind}: {b} span {B["span_us"]} busy {B["busy_us"]} us in {B["launches"]} launches ({B["phases"]} phases)')
    sites = list(dict.fromkeys(list(A['by_site']) + list(B['by_site'])))
    rows = []
    for s in sites:
        x, y = A['by_site'].get(s, 0.0), B['by_site'].get(s, 0.0)
        rows.append(dict(site=s, a_us=round(x, 2), b_us=round(y, 2), delta_us=round(y - x, 2)))
        if abs(y - x) >= 0.3 or kind == 'draft_head':
            print(f'  {s:44s} {x:9.2f} {y:9.2f} {y - x:+8.2f}')
    json.dump(dict(kind=kind, a=a, b=b, A=A, B=B, sites=rows), open(out, 'w'), indent=1)


if __name__ == '__main__':
    main()
