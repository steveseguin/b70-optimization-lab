#!/usr/bin/env python3
"""Tables for research/tp/draft-split-2026-10-29: per-run half/draft medians (rank-0 harness summary.json) and the draft
head split's exchange statistics. Usage: analyze.py RUNS_DIR NAME... > results-*.json"""
import json, statistics as st, sys
from pathlib import Path
runs = Path(sys.argv[1]); out = {}
for name in sys.argv[2:]:
    d = json.loads((runs / name / 'summary.json').read_text())
    half, draft = d['half_ms'][2:], d['draft_ms'][2:]   # as service-ready: medians after the first two steps
    r = dict(tp_env=d['tp_env'], pattern=d['pattern'], steps=d['steps'], prompt=d['prompt'], events=d['events'],
             half_ms_median=round(st.median(half), 4), draft_ms_median=round(st.median(draft), 4),
             stage0_ms=round(st.median(half) + st.median(draft), 4), draft_ms_p10_p90=[round(sorted(draft)[len(draft) // 10], 4), round(sorted(draft)[len(draft) * 9 // 10], 4)])
    s = runs / name / 'rank0' / 'draft-final-state' / 'draft-head-split-exchange.json'
    if s.exists(): r['head_split'] = json.loads(s.read_text())
    x = runs / name / 'rank0' / 'tp-exchange.json'
    if x.exists(): r['target_exchange_timeouts'] = sum(c['timeouts'] + c['abort'] for c in json.loads(x.read_text())['cards'])
    h = runs / name / 'rank0' / 'draft-head-split.json'
    if h.exists(): r['split_rows'] = [json.loads(h.read_text())['card0_rows'], json.loads(h.read_text())['card1_rows']]
    out[name] = r
print(json.dumps(out, indent=1))
