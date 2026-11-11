"""Per-kernel device time by role, mean per step over a group of steps and over a set of cards, for several groups
(diff against the first). Successor of ck2tok/tools/fams.py.
usage: python3 -I fams96.py CARDS LABEL=TIMELINE@s1,s2 [LABEL=TIMELINE@...] ...   (CARDS e.g. 2,5)"""
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from roles96 import T, classify, order_key  # noqa: E402

cards = [int(c) for c in sys.argv[1].split(',')]
cache = {}
groups = []
for a in sys.argv[2:]:
    lab, rest = a.split('=', 1)
    path, st = rest.rsplit('@', 1)
    if path not in cache:
        cache[path] = T.read_timeline(path)
    t = cache[path]
    S = [int(x) for x in st.split(',')]
    acc = defaultdict(lambda: [0.0, 0.0])
    for s in S:
        for c in cards:
            for r, x, _ in classify(t, s, c):
                k = (r, t['names'][x.nid])
                acc[k][0] += (x.de - x.ds) / 1e3 / len(S) / len(cards)
                acc[k][1] += 1 / len(S) / len(cards)
    groups.append((lab, acc))
keys = sorted(set(k for _, a in groups for k in a), key=lambda k: (order_key(k[0]), -groups[0][1].get(k, [0, 0])[0]))
print('cards %s: us per step, launches per step, us per launch' % cards)
print('%-34s' % 'role' + ''.join(' | %-7s %5s %6s' % (lab[:7], 'n', 'us/l') for lab, _ in groups) + ' | kernel')
cur = None
for k in keys:
    r, nm = k
    line = '%-34s' % (r[:34] if r != cur else '')
    cur = r
    for lab, a in groups:
        u, n = a.get(k, [0, 0])
        line += ' | %7.1f %5.1f %6.2f' % (u, n, u / n if n else 0)
    print(line + ' | ' + nm[:150])
print('%-34s' % 'TOTAL' + ''.join(' | %7.1f %5.0f %6s' % (sum(v[0] for v in a.values()), sum(v[1] for v in a.values()), '') for _, a in groups))
