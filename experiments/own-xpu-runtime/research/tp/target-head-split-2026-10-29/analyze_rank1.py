#!/usr/bin/env python3
"""Rank-1 harness tables for research/tp/target-head-split-2026-10-29: per run, the median decode half (steps 3..N, as
service-ready), p10/p90, the split rows and the exchange statistics. Usage: analyze_rank1.py RUNS_DIR NAME... > results-*.json"""
import json, statistics as st, sys
from pathlib import Path
runs = Path(sys.argv[1]); out = {}
for name in sys.argv[2:]:
    d = json.loads((runs / name / 'summary.json').read_text()); h = sorted(d['half_ms'][2:])
    r = dict(tp=d['tp'], pair=d.get('pair'), tp_env=d['tp_env'], steps=d['steps'], prompt=d['prompt'], batched=d['batched'],
             half_ms_median=round(st.median(h), 4), half_ms_p10=round(h[len(h) // 10], 4), half_ms_p90=round(h[len(h) * 9 // 10], 4), tokens=d['tokens'])
    for f, k in (('target-head-split.json', 'split'), ('tp-exchange.json', 'exchange'), ('tp-replicate-compare.json', 'card_compare')):
        p = runs / name / 'rank1' / f
        if p.exists(): r[k] = json.loads(p.read_text())
    out[name] = r
print(json.dumps(out, indent=1))
