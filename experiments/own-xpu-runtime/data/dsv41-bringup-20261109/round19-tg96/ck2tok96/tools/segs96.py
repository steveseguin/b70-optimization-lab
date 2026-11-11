"""(ck2tok96 copy of ck2tok/tools/segs.py on roles96.) Wall-clock segments between exchange completions (causal alignment). For each exchange instance k: arrival per card
(start of the flag-publishing exchange kernel; a preceding XchgPushM is counted as the card's work), completion =
median end over cards. Segment k = completion(k-1) -> completion(k) (first: step start = earliest first launch start).
Per segment kind: wall us per step; the last card's work (its arrival - previous completion); after = completion - last
arrival; the pace card's (c2) and a light card's (c0) work."""
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
cards = sorted(set(k[1] for k in t['L']))
def kindmap(k):
    return {'xchg output-a (pull)': 'A attn in+attn+o_a | output-a', 'xchg output-b': 'B o_b | output-b',
            'xchg expert act (pull)': 'C ffn in+router+gate/up | act', 'xchg ffn rows': 'D down+shared | ffn rows',
            'xchg engram': 'E engram', 'xchg check (draft fc)': 'Z head+check | fc'}.get(k, k)
for g in sys.argv[2:]:
    S = [int(a) for a in g.split(',')]
    W = defaultdict(float); LW = defaultdict(float); AF = defaultdict(float); CW = defaultdict(lambda: defaultdict(float)); N = defaultdict(float)
    TAIL = 0; SPAN = 0
    for s in S:
        per = {}; first = {}; last = {}
        for c in cards:
            cl = classify(t, s, c)
            first[c] = cl[0][1].s; last[c] = max(x.e for _, x in cl)
            ev = []
            for r, x in cl:
                if r.startswith('xchg') and not r.endswith('[PushM]'): ev.append((r, x))
            per[c] = ev
        n = min(len(v) for v in per.values())
        prev = min(first.values()); prevc = {c: first[c] for c in cards}
        for k in range(n):
            kind = kindmap(per[cards[0]][k][0])
            arr = {c: per[c][k][1].s for c in cards}
            comp = st.median(per[c][k][1].e for c in cards)
            la = max(arr.values()); lc = max(arr, key=arr.get)
            W[kind] += (comp - prev) / 1e3; LW[kind] += (la - prev) / 1e3; AF[kind] += (comp - la) / 1e3; N[kind] += 1
            for c in cards: CW[kind][c] += (arr[c] - prev) / 1e3
            prev = comp
        TAIL += (max(last.values()) - prev) / 1e3; SPAN += (max(last.values()) - min(first.values())) / 1e3
    ns = len(S)
    print('steps', S, 'span %.0f us, after the last exchange %.0f us' % (SPAN / ns, TAIL / ns))
    print('%-34s %4s %8s %8s %8s | work before arriving: %s' % ('segment', 'n', 'wall', 'last-arr', 'after', ' '.join('   c%d' % c for c in cards)))
    for kind in sorted(N):
        print('%-34s %4.0f %8.0f %8.0f %8.0f |                       %s' % (kind[:34], N[kind] / ns, W[kind] / ns, LW[kind] / ns, AF[kind] / ns, ' '.join('%5.0f' % (CW[kind][c] / ns) for c in cards)))
    print('%-34s %4s %8.0f %8.0f %8.0f' % ('TOTAL', '', sum(W.values()) / ns + TAIL / ns, sum(LW.values()) / ns, sum(AF.values()) / ns))
    print()
