#!/usr/bin/env python3
"""Per-launch view of the split shapes (CPU only): for every split site label, the one-card time t1 and the card's time
tc (max of the two cards) from the probe traces, and the implied fixed part f = 2*tc - t1 (the time a launch does not
lose when its work halves; t = f + v with v halving). Per role: launches, mean t1, mean tc, mean f. Output:
results/split-fit.json. Inputs: the archived probe runs (one card, card 0 shapes, card 1 shapes)."""
import collections, json, statistics as st, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze as A  # noqa: E402
ARCH = Path('/mnt/raid-models/ownrt-experiment-archives/2026-10-30/stage-overhead-runs-c0-c2')
out = {}
for rank, (one, p0, p1) in {1: ('c1-r1-one', 'c1-r1-p0', 'c1-r1-p1'), 0: ('c1-r0-one', 'c2-r0-p0', 'c2-r0-p1')}.items():
    a, b0, b1 = (A.trace_roles(ARCH / x) for x in (one, p0, p1))
    per = collections.defaultdict(list)
    for label, t1 in a['labels'].items():
        role = A.kind(label)
        if role not in A.TP_SPLIT or label not in b0['labels']:
            continue
        tc = max(b0['labels'][label], b1['labels'].get(label, 0.0))
        per[role].append((label, t1, tc))
    roles = {}
    for role, v in per.items():
        roles[role] = dict(sites=len(v), t1_us=round(st.fmean(x[1] for x in v), 2), tc_us=round(st.fmean(x[2] for x in v), 2),
                           ratio=round(st.fmean(x[2] for x in v) / st.fmean(x[1] for x in v), 3),
                           fixed_us=round(st.fmean(2 * x[2] - x[1] for x in v), 2),
                           fixed_us_range=[round(min(2 * x[2] - x[1] for x in v), 1), round(max(2 * x[2] - x[1] for x in v), 1)])
    out[f'rank{rank}'] = dict(sorted(roles.items(), key=lambda kv: -kv[1]['fixed_us'] * kv[1]['sites']))
    for k, v in out[f'rank{rank}'].items():
        print(rank, k, v)
(HERE / 'results' / 'split-fit.json').write_text(json.dumps(out, indent=1) + '\n')
