import sys, re, statistics as st, collections
# per (card, M): every full kernel name: launches per check, us per launch (median over checks), us per check
# usage: forms_by_m.py timeline spec first_line(1-based spec line of the first check step) cards(e.g. 0,2)
tl, spec, first = sys.argv[1], sys.argv[2], int(sys.argv[3])
cards = [int(c) for c in sys.argv[4].split(',')]
rows = [l.split() for l in open(spec) if l.strip() and not l.startswith('#')]
names = {}
acc = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0.0]))  # (step,card) -> nid -> [n, us]
for ln in open(tl):
    p = ln.split()
    if p[0] == 'kname': names[int(p[1])] = ln.split(None, 2)[2].strip(); continue
    if not p[0][0].isdigit() or len(p) < 13: continue
    c = int(p[1])
    if c not in cards: continue
    a = acc[(int(p[0]), c)][int(p[3])]
    a[0] += 1; a[1] += (int(p[8]) - int(p[7])) / 1e3
steps = sorted(set(k[0] for k in acc))
M = {s: int(rows[first - 1 + (s - steps[0])][5]) + 1 for s in steps}
def short(n):
    n = n.replace('ActF32', 'A').replace('ops41sycl::', '').replace('u,', ',').replace('u>', '>').replace(' ', '')
    return n
for c in cards:
    for m in sorted(set(M.values())):
        ss = [s for s in steps if M[s] == m]
        nids = set(k for s in ss for k in acc[(s, c)])
        tab = []
        for k in nids:
            per = [acc[(s, c)][k][1] if k in acc[(s, c)] else 0.0 for s in ss]
            cnt = [acc[(s, c)][k][0] if k in acc[(s, c)] else 0 for s in ss]
            per1 = [acc[(s, c)][k][1] / acc[(s, c)][k][0] for s in ss if k in acc[(s, c)]]
            tab.append((st.median(per), st.median(cnt), st.median(per1), short(names[k])))
        tab.sort(key=lambda x: -x[0])
        tot = st.median([sum(v[1] for v in acc[(s, c)].values()) for s in ss])
        print(f'== card {c} M={m} checks={len(ss)} busy_median_us={tot:.0f}')
        for t in tab:
            if t[0] >= float(sys.argv[5] if len(sys.argv) > 5 else 5): print(f'{t[0]:8.0f} {t[1]:5.0f} {t[2]:7.2f}  {t[3][:170]}')
