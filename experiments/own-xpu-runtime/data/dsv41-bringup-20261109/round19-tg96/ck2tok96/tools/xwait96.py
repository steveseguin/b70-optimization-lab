"""(ck2tok96 copy of ck2tok/tools/xwait.py on roles96.) Exchange waits from a timeline (causal clock alignment): per exchange instance, each card's arrival (start of the
exchange kernel that publishes its flags: XchgP / XchgPull; a preceding XchgPushM counts as push work), the last
arrival, and per card: wait = last arrival - own arrival (0 for the last), after = end - max(own, last arrival)."""
import sys, statistics as st
from collections import defaultdict
sys.path.insert(0, '/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/engine/tools/perf')
import dsv41_timeline as T
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from roles96 import classify as _cl
def classify(t, s, c):
    return [(r, x) for r, x, _ in _cl(t, s, c)]
t = T.read_timeline(sys.argv[1])
caus = T.align_causal(t, 1000)
for key, v in t['L'].items():
    o = caus[key]
    for x in v: x.s, x.e = x.ds - o, x.de - o
groups = [[int(a) for a in g.split(',')] for g in sys.argv[2:]]
cards = sorted(set(k[1] for k in t['L']))
for S in groups:
    W = defaultdict(lambda: defaultdict(float)); A = defaultdict(lambda: defaultdict(float)); N = defaultdict(float)
    P = defaultdict(lambda: defaultdict(float)); LAST = defaultdict(lambda: defaultdict(float)); LATE = defaultdict(list)
    neg = 0; tot = 0
    for s in S:
        per = {}
        for c in cards:
            xs = [(r, x) for r, x in classify(t, s, c) if r.startswith('xchg')]
            # pair PushM with the following XchgP
            ev = []; push = None
            for r, x in xs:
                if r.endswith('[PushM]'): push = x; continue
                ev.append((r, x, push)); push = None
            per[c] = ev
        n = min(len(v) for v in per.values())
        for k in range(n):
            kind = per[cards[0]][k][0]
            arr = {c: per[c][k][1].s for c in cards}
            la = max(arr.values()); lc = max(arr, key=arr.get)
            srt = sorted(arr.values())
            LAST[kind][lc] += 1; LATE[kind].append((la - srt[-2]) / 1e3)
            N[kind] += 1
            for c in cards:
                r, x, pu = per[c][k]
                w = (la - arr[c]) / 1e3
                af = (x.e - max(arr[c], la)) / 1e3
                tot += 1
                if x.e < la: neg += 1
                W[kind][c] += min(w, (x.e - x.s) / 1e3); A[kind][c] += max(af, 0)
                if pu: P[kind][c] += (pu.e - pu.s) / 1e3
    ns = len(S)
    print('steps', S, ' (exchange ends before the last arrival: %d of %d = alignment error)' % (neg, tot))
    print('%-26s %5s | %s' % ('kind', 'n', ' | '.join('c%d wait/after/push' % c for c in cards)))
    for kind in sorted(N):
        print('%-26s %5.0f | %s' % (kind[:26], N[kind] / ns, ' | '.join('%5.0f %5.0f %4.0f' % (W[kind][c] / ns, A[kind][c] / ns, P[kind][c] / ns) for c in cards)),
              ' last:', ' '.join('c%d %.0f%%' % (c, 100 * LAST[kind][c] / N[kind]) for c in cards if LAST[kind][c]), ' lead med %.1f us' % st.median(LATE[kind]))
    tw = {c: sum(W[k][c] for k in W) / ns for c in cards}; ta = {c: sum(A[k][c] for k in A) / ns for c in cards}; tp = {c: sum(P[k][c] for k in P) / ns for c in cards}
    print('%-26s %5s | %s' % ('TOTAL', '', ' | '.join('%5.0f %5.0f %4.0f' % (tw[c], ta[c], tp[c]) for c in cards)))
    print()
