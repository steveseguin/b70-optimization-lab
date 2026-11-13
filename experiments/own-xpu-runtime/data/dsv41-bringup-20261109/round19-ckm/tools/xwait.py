"""Exchange moving vs waiting per check size from an OWN_TIMELINE_CHECKS file (streamed, small memory).
usage: python3 -I xwait.py timeline spec first_line [out_prefix]
Causal alignment per (step, card): device times shifted so that min(start - submit) = 1 us (dsv41_timeline.py's).
Per exchange instance (k-th exchange launch of the step on every card): arrive = aligned start; last = max arrive;
wait(c) = last - arrive(c); move(c) = end(c) - last (>= 0 part); seg(c) = busy of c's launches since its previous
exchange ended; top(c) = its longest launch there."""
import sys, statistics as st, collections
tl, spec, first = sys.argv[1], sys.argv[2], int(sys.argv[3])
rows = [l.split() for l in open(spec) if l.strip() and not l.startswith('#')]
names = {}
EV = {}  # (step, card) -> list of exchange events
def flush(key, L):
    if not L: return
    L.sort()
    off = min(ds - sub for (_, _, sub, ds, de, _, _) in L) - 1000
    ev = []; seg = 0.0; top = (0.0, -1); segn = []
    for (idx, nid, sub, ds, de, xp, xm) in L:
        d = (de - ds) / 1e3
        if names.get(nid, '').startswith('Xchg'):
            ev.append((ds - off, de - off, xp, xm, nid, seg, top[1], top[0]))
            seg = 0.0; top = (0.0, -1)
        else:
            seg += d
            if d > top[0]: top = (d, nid)
    EV[key] = ev
cur = None; L = []
for ln in open(tl):
    p = ln.split()
    if not p: continue
    if p[0] == 'kname': names[int(p[1])] = ln.split(None, 2)[2].strip(); continue
    if not p[0][0].isdigit() or len(p) < 13: continue
    key = (int(p[0]), int(p[1]))
    if key != cur:
        flush(cur, L); cur = key; L = []
    L.append((int(p[2]), int(p[3]), int(p[4]), int(p[7]), int(p[8]), int(p[10]), int(p[11])))
flush(cur, L); L = None
steps = sorted(set(k[0] for k in EV)); cards = sorted(set(k[1] for k in EV))
M = {s: int(rows[first - 1 + (s - steps[0])][5]) + 1 for s in steps}
# per step: matched instances
XPN = {0: 'out-a', 1: 'rows', 2: 'act', 3: 'engram', 5: 'out-a blk', -1: 'other'}
per = collections.defaultdict(lambda: collections.defaultdict(list))  # M -> quantity -> list per step
lastcnt = collections.defaultdict(collections.Counter)  # M -> card -> times last
lastby = collections.defaultdict(lambda: collections.defaultdict(float))  # M -> card -> sum of (last - second last) us
bypart = collections.defaultdict(lambda: collections.defaultdict(lambda: [0.0, 0.0, 0]))  # M -> (xp, card) -> [wait, move, n]
topw = collections.defaultdict(collections.Counter)  # M -> top kernel of the last card weighted by its lead (us)
bad = 0
for s in steps:
    n = set(len(EV.get((s, c), [])) for c in cards)
    if len(n) != 1: bad += 1; continue
    m = M[s]
    W = collections.defaultdict(float); MV = collections.defaultdict(float); TOT = collections.defaultdict(float)
    endspread = []
    for k in range(n.pop()):
        e = {c: EV[(s, c)][k] for c in cards}
        arr = {c: e[c][0] for c in cards}
        last = max(arr.values())
        lc = max(cards, key=lambda c: arr[c])
        second = sorted(arr.values())[-2]
        lastcnt[m][lc] += 1
        lastby[m][lc] += (last - second) / 1e3
        nm = names.get(e[lc][6], '?') if e[lc][6] >= 0 else '-'
        topw[m][nm[:90]] += (last - second) / 1e3
        ends = [e[c][1] for c in cards]
        endspread.append((max(ends) - min(ends)) / 1e3)
        for c in cards:
            w = (last - arr[c]) / 1e3
            mv = max(0.0, (e[c][1] - last) / 1e3)
            W[c] += w; MV[c] += mv; TOT[c] += (e[c][1] - e[c][0]) / 1e3
            b = bypart[m][(e[c][2], c)]; b[0] += w; b[1] += mv; b[2] += 1
    for c in cards:
        per[m][('wait', c)].append(W[c]); per[m][('move', c)].append(MV[c]); per[m][('xtot', c)].append(TOT[c])
    per[m][('endspread', -1)].append(st.median(endspread))
print('steps', len(steps), 'unmatched', bad)
Ms = sorted(set(M.values()))
print('\nPer check (median over checks), exchange time per card split into WAIT (for the last card to arrive) and MOVE (after it arrived), us')
print('M  n   ' + ''.join(f'  c{c}:tot/wait/move    ' for c in cards))
for m in Ms:
    nn = len(per[m][('wait', cards[0])])
    print(f'{m}  {nn:2d}  ' + ''.join(f'{st.median(per[m][("xtot", c)]):6.0f}/{st.median(per[m][("wait", c)]):5.0f}/{st.median(per[m][("move", c)]):5.0f}   ' for c in cards))
print('\nexchange end spread across cards (median per check of the per-instance max-min end, us):', {m: round(st.median(per[m][('endspread', -1)]), 2) for m in Ms})
print('\nWho arrives last (instances per check) and by how much it trails the second-last (sum per check, us)')
for m in Ms:
    nn = len(per[m][('wait', cards[0])])
    print(f'M={m}: ' + '  '.join(f'c{c} {lastcnt[m][c]/nn:5.1f}x {lastby[m][c]/nn:6.0f}us' for c in cards))
print('\nPer exchange part: wait / move per check (us), card by card')
for m in Ms:
    nn = len(per[m][('wait', cards[0])])
    xps = sorted(set(k[0] for k in bypart[m]))
    for xp in xps:
        print(f'M={m} {XPN.get(xp, xp):>9}: ' + '  '.join(f'c{c} {bypart[m][(xp, c)][0]/nn:5.0f}/{bypart[m][(xp, c)][1]/nn:5.0f} ({bypart[m][(xp, c)][2]/nn:3.0f})' for c in cards))
print('\nLongest launch before the exchange on the last-arriving card, weighted by its lead over the second-last (us per check)')
for m in Ms:
    nn = len(per[m][('wait', cards[0])])
    print(f'M={m}: ' + '; '.join(f'{v/nn:.0f} {k}' for k, v in topw[m].most_common(8)))
