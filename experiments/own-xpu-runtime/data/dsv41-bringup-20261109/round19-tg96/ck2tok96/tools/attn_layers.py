"""Attention core per layer, two one-token timelines (e.g. defaults against OWN_ATT_T=1): us per layer (mean over the
steps and the cards given), launches, and the slot count of the layer (n in SparseOutF<512u, n, ..> or
SparseSoftmaxP<n> / SparseSoftmaxPN; 128 = window only).
usage: python3 -I attn_layers.py A.txt B.txt STEPS CARDS   (STEPS e.g. 20-27, CARDS e.g. 2,5)"""
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from roles96 import T, classify  # noqa: E402

a, b, st, cs = sys.argv[1:5]
s0, s1 = (int(x) for x in st.split('-'))
steps = list(range(s0, s1 + 1))
cards = [int(c) for c in cs.split(',')]


def per_layer(path):
    t = T.read_timeline(path)
    us = defaultdict(float)
    n = defaultdict(float)
    slots = defaultdict(set)
    names = defaultdict(set)
    for s in steps:
        for c in cards:
            for r, x, L in classify(t, s, c):
                if r != 'attention core':
                    continue
                nm = t['names'][x.nid]
                us[L] += (x.de - x.ds) / 1e3 / len(steps) / len(cards)
                n[L] += 1 / len(steps) / len(cards)
                m = re.search(r'SparseOutF<512u, (\d+)|SparseSoftmaxP<(\d+)>|SparseOutJE<512u, (\d+)', nm)
                if m:
                    slots[L].add(int(next(g for g in m.groups() if g)))
                elif 'SparseSoftmaxPN' in nm:
                    slots[L].add(-1)
                names[L].add(re.sub(r'<.*', '', nm))
    return us, n, slots, names


A = per_layer(a)
B = per_layer(b)
print('%5s %10s %8s %5s %8s %5s %8s  %s' % ('layer', 'slots', 'A us', 'n', 'B us', 'n', 'B-A', 'B kernels'))
tot = defaultdict(lambda: [0, 0, 0])
for L in sorted(set(A[0]) | set(B[0])):
    sl = sorted(B[2][L] | A[2][L])
    key = 'window only' if sl == [128] else 'window + compressed'
    tot[key][0] += A[0][L]
    tot[key][1] += B[0][L]
    tot[key][2] += 1
    print('%5d %10s %8.1f %5.1f %8.1f %5.1f %+8.1f  %s' % (L, ','.join(str(x) for x in sl), A[0][L], A[1][L], B[0][L],
                                                          B[1][L], B[0][L] - A[0][L], ' '.join(sorted(B[3][L]))))
for k, (x, y, n) in tot.items():
    print('%s: %d layers, A %.1f us (%.2f per layer), B %.1f us (%.2f per layer), B-A %+.1f us per step' %
          (k, n, x, x / n, y, y / n, y - x))
