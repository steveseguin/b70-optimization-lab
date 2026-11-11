"""Routed expert launches per format against their byte floor, per check size M (pace cards 2, 5 mean), pooled over
timelines. Floor per launch = the mean distinct experts of that format's layers (OWN_MT_IDDUMP, consecutive tokens)
x bytes per expert and card (floor_experts.py's sizes, pace card: down rows 864) / BW.
usage: python3 -I experts_vs_floor.py IDDUMP BW M=TIMELINE@s1,s2 [M=TIMELINE@...] ..."""
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from roles96 import T, classify  # noqa: E402
from floor_experts import BLK, fmt_of  # noqa: E402  (module runs nothing on import: guarded below)

dump, bw = sys.argv[1], float(sys.argv[2])
cache = {}
data = collections.defaultdict(list)
for a in sys.argv[3:]:
    m, rest = a.split('=', 1)
    path, st = rest.rsplit('@', 1)
    if path not in cache:
        cache[path] = T.read_timeline(path)
    for s in st.split(','):
        data[int(m)].append((cache[path], int(s)))
Ms = sorted(data)
per_layer = collections.defaultdict(list)
with open(dump) as f:
    for line in f:
        v = line.split()
        if len(v) < 2:
            continue
        L, M = int(v[0]), int(v[1])
        ids = [int(x) for x in v[2:]]
        for i in range(M):
            per_layer[L].append(tuple(ids[6 * i:6 * i + 6]))


def distinct(L, M):
    toks = per_layer[L]
    n = len(toks) // M
    return sum(len(set(e for tk in toks[b * M:(b + 1) * M] for e in tk)) for b in range(n)) / n


meas = collections.defaultdict(lambda: collections.defaultdict(lambda: [0.0, 0]))  # (kind, fmt) -> M -> [us, n]
layers_of = collections.defaultdict(set)
for m in Ms:
    for t, s in data[m]:
        for c in (2, 5):
            for r, x, L in classify(t, s, c):
                if r not in ('experts gate+up', 'experts down'):
                    continue
                k = ('gate+up' if r == 'experts gate+up' else 'down', fmt_of(t['names'][x.nid]))
                meas[k][m][0] += (x.de - x.ds) / 1e3
                meas[k][m][1] += 1
                layers_of[k].add(L)
print('pace cards: us per launch measured / floor at %.0f GB/s (ratio), per check size' % bw)
print('%-16s %3s' % ('kind format', 'L') + ''.join('%22s' % ('M=%d' % m) for m in Ms) + '   slope/token meas / floor')
for k in sorted(meas):
    Ls = sorted(layers_of[k])
    rows = 768 * 20 if k[0] == 'gate+up' else 864 * 9
    line = '%-16s %3d' % ('%s %s' % k, len(Ls))
    ms, fs = [], []
    for m in Ms:
        u, n = meas[k][m]
        us = u / n if n else 0
        fl = sum(distinct(L, m) for L in Ls) / len(Ls) * rows * BLK[k[1]] / (bw * 1e3)
        ms.append(us)
        fs.append(fl)
        line += '   %6.1f / %5.1f (%3.1f)' % (us, fl, us / fl if fl else 0)
    sm = (ms[-1] - ms[0]) / (Ms[-1] - Ms[0])
    sf = (fs[-1] - fs[0]) / (Ms[-1] - Ms[0])
    print(line + '   %5.1f / %4.1f us (%3.1f)' % (sm, sf, sm / sf if sf else 0))
