"""Per-role device time against the check size M, pooled over timelines (OWN_TIMELINE_CHECKS), for the pace cards
(2, 5) and the light cards (0, 1, 3, 4); the step span (causal alignment, earliest start -> latest end); the
least-squares slope per token over the sizes given, and the step-by-step increments.
usage: python3 -I slope96.py M=TIMELINE@s1,s2 [M=TIMELINE@...] ...   (M = the check's tokens; repeat M to pool)"""
import os
import statistics as stt
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from roles96 import T, classify, order_key  # noqa: E402

P = [2, 5]
LC = [0, 1, 3, 4]
cache = {}
data = defaultdict(list)  # M -> list of (t, step)
for a in sys.argv[1:]:
    m, rest = a.split('=', 1)
    path, st = rest.rsplit('@', 1)
    if path not in cache:
        t = T.read_timeline(path)
        caus = T.align_causal(t, 1000)
        for key, v in t['L'].items():
            o = caus[key]
            for x in v:
                x.s, x.e = x.ds - o, x.de - o
        cache[path] = t
    for s in st.split(','):
        data[int(m)].append((cache[path], int(s)))
Ms = sorted(data)
role = {k: defaultdict(lambda: defaultdict(float)) for k in ('pace', 'light')}
span = {}
for m in Ms:
    sp = []
    for t, s in data[m]:
        cards = sorted(c for (st, c) in t['L'] if st == s)
        sp.append((max(max(x.e for x in t['L'][(s, c)]) for c in cards) - min(t['L'][(s, c)][0].s for c in cards)) / 1e3)
        for kind, cs in (('pace', P), ('light', LC)):
            for c in cs:
                for r, x, _ in classify(t, s, c):
                    role[kind][r][m] += (x.de - x.ds) / 1e3 / len(data[m]) / len(cs)
    span[m] = stt.mean(sp)


def slope(ys):
    xs = Ms
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    vx = sum((a - mx) ** 2 for a in xs)
    return sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / vx if vx else 0.0


print('checks per size: ' + ', '.join('M=%d: %d' % (m, len(data[m])) for m in Ms))
print('%-40s' % 'step span (us)' + ''.join('%8.0f' % span[m] for m in Ms) + '   slope %7.1f' % slope([span[m] for m in Ms])
      + '  steps ' + ' '.join('%+6.0f' % (span[b] - span[a]) for a, b in zip(Ms, Ms[1:])))
for kind in ('pace', 'light'):
    R = role[kind]
    print()
    print('%s cards: us per check' % kind)
    print('%-40s' % 'role' + ''.join('%8s' % ('M=%d' % m) for m in Ms) + '   %13s' % 'slope/token' + '  steps')
    keys = sorted(R, key=order_key)
    tot = [0.0] * len(Ms)
    for k in keys:
        ys = [R[k].get(m, 0.0) for m in Ms]
        tot = [a + b for a, b in zip(tot, ys)]
        print('%-40s' % k[:40] + ''.join('%8.0f' % y for y in ys) + '   %13.1f' % slope(ys) + '  '
              + ' '.join('%+6.0f' % (b - a) for a, b in zip(ys, ys[1:])))
    print('%-40s' % 'TOTAL busy' + ''.join('%8.0f' % y for y in tot) + '   %13.1f' % slope(tot) + '  '
          + ' '.join('%+6.0f' % (b - a) for a, b in zip(tot, tot[1:])))
