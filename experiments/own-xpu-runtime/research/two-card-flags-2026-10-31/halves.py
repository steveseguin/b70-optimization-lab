#!/usr/bin/env python3
"""Half wall times per arm (summary.json: rank 0 spec_ms, rank 1 half_ms; medians over halves 3..), A/B pairs.
Usage: halves.py RUNS_DIR OUT.json ARM...   prints one line per arm and writes OUT.json."""
import json, statistics as st, sys
from pathlib import Path
runs, out, arms = Path(sys.argv[1]), sys.argv[2], sys.argv[3:]
res = {}
for a in arms:
    s = json.loads((runs / a / 'summary.json').read_text())
    h = s.get('spec_ms') or s.get('half_ms') or []
    d = s.get('draft_ms') or []
    hk = None
    for r in ('rank0', 'rank1'):
        p = runs / a / r / 'hc-kernels.json'
        if p.exists(): hk = json.loads(p.read_text())
    res[a] = dict(half_median_ms=round(st.median(h[2:]), 4) if len(h) > 3 else None, halves=len(h),
                  p10=round(sorted(h[2:])[len(h[2:]) // 10], 4) if len(h) > 12 else None,
                  p90=round(sorted(h[2:])[9 * len(h[2:]) // 10], 4) if len(h) > 12 else None,
                  draft_median_ms=round(st.median(d[2:]), 4) if len(d) > 3 else None, hc_kernels=hk)
    print(a, res[a])
json.dump(res, open(out, 'w'), indent=1)
