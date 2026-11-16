#!/usr/bin/env python3
# tlcmp.py A.txt B.txt [CARD]: per-kernel GPU time per answer step (OWN_TIMELINE files), A against B, on one card
# (default 2) and the mean over cards: which launches grow with the context. Stdlib only; python3 -I.
import sys
from collections import defaultdict
def load(p):
    names, per = {}, defaultdict(lambda: defaultdict(float))  # per[card][name] = total ns
    steps = defaultdict(set); cnt = defaultdict(lambda: defaultdict(int))
    for ln in open(p):
        f = ln.split()
        if not f or f[0].startswith('#'): continue
        if f[0] == 'kname': names[int(f[1])] = ' '.join(f[2:]); continue
        if not f[0].lstrip('-').isdigit() or len(f) < 14: continue
        st, c, kid = int(f[0]), int(f[1]), int(f[3])
        d = int(f[8]) - int(f[7])
        nm = names.get(kid, str(kid))
        per[c][nm] += d; cnt[c][nm] += 1; steps[c].add(st)
    return per, cnt, steps
def short(n):
    n = n.replace('ops41sycl::', '').replace('<ActF32>', '')
    return n if len(n) <= 70 else n[:67] + '...'
A, B = sys.argv[1], sys.argv[2]; card = int(sys.argv[3]) if len(sys.argv) > 3 else 2
pa, ca, sa = load(A); pb, cb, sb = load(B)
def tab(c_list, label):
    ga, gb = defaultdict(float), defaultdict(float); na, nb = defaultdict(float), defaultdict(float)
    for c in c_list:
        for k, v in pa[c].items(): ga[k] += v / len(sa[c]) / len(c_list) / 1e6; na[k] += cnt_a(c, k)
        for k, v in pb[c].items(): gb[k] += v / len(sb[c]) / len(c_list) / 1e6; nb[k] += cnt_b(c, k)
    ta, tb = sum(ga.values()), sum(gb.values())
    print(f"== {label}: busy per step A {ta:.3f} ms, B {tb:.3f} ms, B - A {tb - ta:+.3f} ms")
    rows = sorted(set(ga) | set(gb), key=lambda k: -(gb.get(k, 0) - ga.get(k, 0)))
    print(f"{'ms A':>8} {'ms B':>8} {'B-A':>8} {'n/step A':>8} {'B':>6}  launch")
    for k in rows[:22]:
        print(f"{ga.get(k,0):8.3f} {gb.get(k,0):8.3f} {gb.get(k,0)-ga.get(k,0):+8.3f} {na.get(k,0)/max(1,sum(len(sa[c]) for c in c_list)):8.1f} {nb.get(k,0)/max(1,sum(len(sb[c]) for c in c_list)):6.1f}  {short(k)}")
def cnt_a(c, k): return ca[c][k]
def cnt_b(c, k): return cb[c][k]
tab([card], f"card {card}")
tab(sorted(set(pa) & set(pb)), "mean over cards")
