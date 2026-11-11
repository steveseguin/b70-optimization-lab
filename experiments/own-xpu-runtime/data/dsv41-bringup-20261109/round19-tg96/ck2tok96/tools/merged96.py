"""Pace (cards 2, 5: 16 heads at checks and one-token steps) against light cards (0, 1, 3, 4), per role, for groups
of steps that may come from different timelines. Successor of ck2tok/tools/merged.py.
usage: python3 -I merged96.py LABEL=TIMELINE@s1,s2,... [LABEL=TIMELINE@...] ...
Prints us per step (mean over the group's steps and the cards of each kind) and launches; diff columns are against
the first group."""
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from roles96 import T, table, order_key  # noqa: E402

P = [2, 5]
LC = [0, 1, 3, 4]
cache = {}
groups = []
for a in sys.argv[1:]:
    lab, rest = a.split('=', 1)
    path, st = rest.rsplit('@', 1)
    if path not in cache:
        cache[path] = T.read_timeline(path)
    S = [int(x) for x in st.split(',')]
    groups.append((lab, table(cache[path], S, P + LC)))


def avg(r, cs, k):
    return (sum(r[c].get(k, [0, 0])[0] for c in cs) / len(cs), sum(r[c].get(k, [0, 0])[1] for c in cs) / len(cs))


keys = []
for _, r in groups:
    for c in P + LC:
        for k in r[c]:
            if k not in keys:
                keys.append(k)
keys.sort(key=order_key)
for kind, cs in (('pace cards 2+5', P), ('light cards 0,1,3,4', LC)):
    print('%s (us per step, launches; d = against %s)' % (kind, groups[0][0]))
    hdr = '%-40s' % 'role'
    for i, (lab, _) in enumerate(groups):
        hdr += ' | %8s %5s' % (lab[:8], 'n') + ('' if i == 0 else ' %6s' % 'd')
    print(hdr)
    tot = [[0.0, 0.0] for _ in groups]
    for k in keys:
        line = '%-40s' % k[:40]
        b0 = avg(groups[0][1], cs, k)[0]
        for i, (lab, r) in enumerate(groups):
            u, n = avg(r, cs, k)
            tot[i][0] += u
            tot[i][1] += n
            line += ' | %8.0f %5.0f' % (u, n) + ('' if i == 0 else ' %+6.0f' % (u - b0))
        print(line)
    line = '%-40s' % 'TOTAL busy'
    for i in range(len(groups)):
        line += ' | %8.0f %5.0f' % (tot[i][0], tot[i][1]) + ('' if i == 0 else ' %+6.0f' % (tot[i][0] - tot[0][0]))
    print(line)
    print()
