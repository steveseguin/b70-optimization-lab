"""Per-check device time by kernel family against the check size (OWN_TIMELINE_CHECKS timeline + OWN_SPEC_LOG of the same run).
usage: python3 -I ck_by_m.py timeline.txt spec.txt first_check_index [card]"""
import sys, os, re
sys.path.insert(0, '/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/engine/tools/perf')
import dsv41_timeline as T
from dsv41_kbusy import fam
from collections import defaultdict
tl, spec, first = sys.argv[1], sys.argv[2], int(sys.argv[3])
card = int(sys.argv[4]) if len(sys.argv) > 4 else 2
rows = [l.split() for l in open(spec) if l.strip() and not l.startswith('#')]
t = T.read_timeline(tl)
steps = sorted(set(k[0] for k in t['L']))
print('steps in timeline:', steps[:3], '...', len(steps))
per = {}
for i, s in enumerate(steps):
    acc = defaultdict(float)
    for x in t['L'].get((s, card), []):
        acc[fam(t['names'].get(x.nid, '?'))] += (x.de - x.ds) / 1e3
    per[s] = acc
# map step i -> spec row first+i: guesses = 5th from last column
ms = {}
for i, s in enumerate(steps):
    r = rows[first + i]
    ms[s] = int(r[-5]) + 1
fams = sorted(set(k for a in per.values() for k in a), key=lambda k: -sum(per[s].get(k, 0) for s in steps))
print('M per check:', [ms[s] for s in steps])
print('%-56s' % 'family' + ''.join('%8s' % ('M=%d' % ms[s]) for s in steps) + '   slope/token')
tot = defaultdict(float)
for k in fams[:40]:
    xs = [ms[s] for s in steps]; ys = [per[s].get(k, 0) for s in steps]
    n = len(xs); mx = sum(xs) / n; my = sum(ys) / n
    vx = sum((a - mx) ** 2 for a in xs)
    sl = sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / vx if vx else 0
    print('%-56s' % k[:56] + ''.join('%8.0f' % y for y in ys) + '   %8.1f' % sl)
xs = [ms[s] for s in steps]; ys = [sum(per[s].values()) for s in steps]
n = len(xs); mx = sum(xs) / n; my = sum(ys) / n; vx = sum((a - mx) ** 2 for a in xs)
sl = sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / vx if vx else 0
print('%-56s' % 'TOTAL busy' + ''.join('%8.0f' % y for y in ys) + '   %8.1f' % sl)
