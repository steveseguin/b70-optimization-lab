#!/usr/bin/env python3
"""Compare a rank-1 state dump at a small context (A) with one at a larger context (B), same inputs.
Same-size buffers must be byte-identical. A buffer that is k times larger in B must hold A's bytes as its prefix
(position-major layout) and zeros after it. Prints a JSON summary; exit 1 on any difference."""
import json, sys
def index(d):
    rows = {}
    for line in open(d + '/rank1/state-2147483647/state-index.tsv'):
        p = line.rstrip('\n').split('\t')
        if len(p) == 4 and p[1].isdigit(): rows[p[0]] = (int(p[1]), int(p[2]), p[3])
    return rows
a, b = sys.argv[1], sys.argv[2]
ia, ib = index(a), index(b)
fa = open(a + '/rank1/state-2147483647/state.bundle', 'rb'); fb = open(b + '/rank1/state-2147483647/state.bundle', 'rb')
same = grown = 0; bad = []
for name in sorted(ia.keys() | ib.keys()):
    if name not in ia or name not in ib: bad.append((name, 'missing')); continue
    (oa, na, ha), (ob, nb, hb) = ia[name], ib[name]
    if na == nb:
        if ha != hb: bad.append((name, 'differs')); continue
        same += 1; continue
    if nb % na or nb < na: bad.append((name, f'size {na}->{nb}')); continue
    fa.seek(oa); xa = fa.read(na); fb.seek(ob); xb = fb.read(nb)
    if xb[:na] != xa: bad.append((name, 'prefix differs')); continue
    if xb[na:].count(0) != nb - na: bad.append((name, 'tail not zero')); continue
    grown += 1
sa, sb = json.load(open(a + '/summary.json')), json.load(open(b + '/summary.json'))
print(json.dumps(dict(buffers=len(ia), identical=same, grown_prefix_equal_tail_zero=grown, differences=bad[:30],
                      difference_count=len(bad), tokens_equal=sa['tokens'] == sb['tokens'],
                      half_ms_median=[sorted(s['half_ms'])[len(s['half_ms']) // 2] for s in (sa, sb)])))
sys.exit(1 if bad or sa['tokens'] != sb['tokens'] else 0)
