"""Per check size and card: span (first launch start -> last end, device clock), busy, the gaps between consecutive
launches (count > 0.5 us, sum) and the launches that sit between two such gaps (register-mode change signature: a
256-register kernel between 128-register ones), streamed.
usage: python3 -I gaps.py timeline spec first_line cards"""
import sys, statistics as st, collections
tl, spec, first = sys.argv[1], sys.argv[2], int(sys.argv[3])
cards = [int(c) for c in sys.argv[4].split(',')]
rows = [l.split() for l in open(spec) if l.strip() and not l.startswith('#')]
names = {}
OUT = {}
def flush(key, L):
    if not L or key[1] not in cards: return
    L.sort()
    span = (L[-1][3] - L[0][2]) / 1e3
    busy = sum(de - ds for (_, _, ds, de) in L) / 1e3
    g = [(L[i + 1][2] - L[i][3]) / 1e3 for i in range(len(L) - 1)]
    big = [x for x in g if x > 0.5]
    sand = collections.Counter()
    sandus = collections.Counter()
    for i in range(1, len(L) - 1):
        if g[i - 1] > 0.5 and g[i] > 0.5:
            nm = names.get(L[i][1], '?')
            sand[nm] += 1; sandus[nm] += g[i - 1] + g[i]
    OUT[key] = (span, busy, len(big), sum(big), sum(x for x in g if 0 < x <= 0.5), sand, sandus)
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
steps = sorted(set(k[0] for k in OUT))
M = {s: int(rows[first - 1 + (s - steps[0])][5]) + 1 for s in steps}
for c in cards:
    for m in sorted(set(M.values())):
        ss = [s for s in steps if M[s] == m and (s, c) in OUT]
        v = [OUT[(s, c)] for s in ss]
        print(f'card {c} M={m} n={len(ss)}: span {st.median([x[0] for x in v])/1e3:6.3f} ms busy {st.median([x[1] for x in v])/1e3:6.3f}'
              f' | gaps>0.5us: {st.median([x[2] for x in v]):4.0f} sum {st.median([x[3] for x in v]):5.0f} us | small gaps sum {st.median([x[4] for x in v]):5.0f} us')
        sand = collections.Counter(); sandus = collections.Counter()
        for x in v: sand.update(x[5]); sandus.update(x[6])
        top = sandus.most_common(14)
        print('     between two big gaps (per check: launches, gap us): ' + '; '.join(f'{sand[k]/len(v):.0f} {sandus[k]/len(v):.0f}us {k[:70]}' for k, _ in top))
