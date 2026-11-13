"""Per check size: each card's compute (non-exchange busy, ms), the critical-path estimate sum over exchange segments of
max_c(segment compute) + move, and how often / by how much each card is the segment maximum (streamed).
usage: python3 -I xseg.py timeline spec first_line"""
import sys, statistics as st, collections
tl, spec, first = sys.argv[1], sys.argv[2], int(sys.argv[3])
rows = [l.split() for l in open(spec) if l.strip() and not l.startswith('#')]
names = {}
SEG = {}
def flush(key, L):
    if not L: return
    L.sort()
    segs = []; seg = 0.0; xs = []
    for (idx, nid, ds, de) in L:
        d = (de - ds) / 1e3
        if names.get(nid, '').startswith('Xchg'):
            segs.append(seg); xs.append(d); seg = 0.0
        else: seg += d
    segs.append(seg)
    SEG[key] = (segs, xs)
cur = None; L = []
for ln in open(tl):
    p = ln.split()
    if not p: continue
    if p[0] == 'kname': names[int(p[1])] = ln.split(None, 2)[2].strip(); continue
    if not p[0][0].isdigit() or len(p) < 13: continue
    key = (int(p[0]), int(p[1]))
    if key != cur: flush(cur, L); cur = key; L = []
    L.append((int(p[2]), int(p[3]), int(p[7]), int(p[8])))
flush(cur, L)
steps = sorted(set(k[0] for k in SEG)); cards = sorted(set(k[1] for k in SEG))
M = {s: int(rows[first - 1 + (s - steps[0])][5]) + 1 for s in steps}
R = collections.defaultdict(lambda: collections.defaultdict(list))
for s in steps:
    m = M[s]
    n = set(len(SEG[(s, c)][0]) for c in cards)
    if len(n) != 1: continue
    n = n.pop()
    comp = {c: sum(SEG[(s, c)][0]) for c in cards}
    crit = 0.0; mx = collections.Counter(); lead = collections.Counter(); minx = 0.0
    for k in range(n):
        v = {c: SEG[(s, c)][0][k] for c in cards}
        top = max(cards, key=lambda c: v[c]); crit += v[top]
        srt = sorted(v.values()); mx[top] += 1; lead[top] += srt[-1] - srt[-2]
        if k < n - 1: minx += min(SEG[(s, c)][1][k] for c in cards)
    for c in cards:
        R[m][('comp', c)].append(comp[c]); R[m][('max', c)].append(mx[c]); R[m][('lead', c)].append(lead[c])
    R[m][('crit',)].append(crit); R[m][('minx',)].append(minx)
for m in sorted(R):
    n = len(R[m][('crit',)])
    print(f'M={m} n={n}: compute ms ' + ' '.join(f'c{c} {st.median(R[m][("comp", c)])/1e3:5.2f}' for c in cards) +
          f' | sum of segment max {st.median(R[m][("crit",)])/1e3:5.2f} + min-card exchange {st.median(R[m][("minx",)])/1e3:5.2f}')
    print('      segment max on card (times / lead over 2nd, us): ' + ' '.join(f'c{c} {st.median(R[m][("max", c)]):3.0f}/{st.median(R[m][("lead", c)]):4.0f}' for c in cards))
