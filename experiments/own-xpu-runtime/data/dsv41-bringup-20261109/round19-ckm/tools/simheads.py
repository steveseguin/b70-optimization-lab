"""Simulate moving the 16-head groups (whole groups) from cards 2 / 5 to other cards, from an OWN_TIMELINE_CHECKS file.
Per check and exchange segment k (launches between two exchanges), card c's compute t(c,k). Speed factor f(c) per
check = sum of c's compute over the segments NOT ending at the output-a exchange / card 0's. Segments ending at an
output-a exchange (xpart 0: q_b, rope, attention, output-a, the DSPLIT partials) are the head-dependent ones: in the
new layout card c (new role) takes the instance value of a card of that role today, scaled by f(c) / f(donor).
Critical path = sum over segments of max_c t(c,k) + the smallest card's exchange time (as xseg.py).
usage: python3 -I simheads.py timeline spec first_line heavy_new (e.g. 0,3)"""
import sys, statistics as st, collections
tl, spec, first = sys.argv[1], sys.argv[2], int(sys.argv[3])
new = [int(c) for c in sys.argv[4].split(',')]
rows = [l.split() for l in open(spec) if l.strip() and not l.startswith('#')]
names = {}
SEG = {}
def flush(key, L):
    if not L: return
    L.sort()
    segs = []; seg = 0.0
    for (idx, nid, ds, de, xp) in L:
        d = (de - ds) / 1e3
        if names.get(nid, '').startswith('Xchg'):
            segs.append((seg, xp, d)); seg = 0.0
        else: seg += d
    segs.append((seg, -9, 0.0))
    SEG[key] = segs
cur = None; L = []
for ln in open(tl):
    p = ln.split()
    if not p: continue
    if p[0] == 'kname': names[int(p[1])] = ln.split(None, 2)[2].strip(); continue
    if not p[0][0].isdigit() or len(p) < 13: continue
    key = (int(p[0]), int(p[1]))
    if key != cur: flush(cur, L); cur = key; L = []
    L.append((int(p[2]), int(p[3]), int(p[7]), int(p[8]), int(p[10])))
flush(cur, L)
steps = sorted(set(k[0] for k in SEG)); cards = sorted(set(k[1] for k in SEG))
M = {s: int(rows[first - 1 + (s - steps[0])][5]) + 1 for s in steps}
old = [2, 5]
light_old = [c for c in cards if c not in old]
# donors: new heavy card i takes old heavy card old[i]'s values; old heavy cards take the new heavy cards' old values
donor = {c: c for c in cards}
for a, b in zip(new, old):
    donor[a] = b; donor[b] = a
R = collections.defaultdict(lambda: collections.defaultdict(list))
for s in steps:
    m = M[s]
    n = set(len(SEG[(s, c)]) for c in cards)
    if len(n) != 1: continue
    n = n.pop()
    f = {}
    base = {c: sum(SEG[(s, c)][k][0] for k in range(n) if SEG[(s, c)][k][1] != 0) for c in cards}
    for c in cards: f[c] = base[c] / base[0]
    crit0 = crit1 = 0.0; minx = 0.0; att0 = att1 = 0.0
    for k in range(n):
        xp = SEG[(s, cards[0])][k][1]
        t = {c: SEG[(s, c)][k][0] for c in cards}
        crit0 += max(t.values())
        if xp == 0:
            t1 = {c: t[donor[c]] * f[c] / f[donor[c]] for c in cards}
            att0 += max(t.values()); att1 += max(t1.values())
        else: t1 = t
        crit1 += max(t1.values())
        if k < n - 1: minx += min(SEG[(s, c)][k][2] for c in cards)
    R[m]['crit0'].append(crit0 + minx); R[m]['crit1'].append(crit1 + minx); R[m]['att0'].append(att0); R[m]['att1'].append(att1)
    for c in cards: R[m][('f', c)].append(f[c])
mix = {1: 32, 2: 30, 3: 20, 4: 6, 5: 8, 6: 4}
tot = 0.0
print(f'heavy cards 2,5 -> {new}; per check, ms (median over checks)')
for m in sorted(R):
    a, b = st.median(R[m]['crit0']), st.median(R[m]['crit1'])
    d = st.median([x - y for x, y in zip(R[m]['crit0'], R[m]['crit1'])])
    tot += mix.get(m, 0) / 100 * d
    print(f'M={m} n={len(R[m]["crit0"]):2d}: critical path {a/1e3:6.3f} -> {b/1e3:6.3f} (saving {d/1e3:5.3f}); attention segments max sum '
          f'{st.median(R[m]["att0"])/1e3:5.3f} -> {st.median(R[m]["att1"])/1e3:5.3f}; speed f(c) vs card 0 (non-attention segments): ' +
          ' '.join(f'c{c} {st.median(R[m][("f", c)]):.3f}' for c in cards))
print(f'tl105 mix: saving {tot/1e3:.3f} ms per average check')
