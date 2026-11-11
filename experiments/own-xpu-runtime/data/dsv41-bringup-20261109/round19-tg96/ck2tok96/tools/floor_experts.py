"""Byte floor of the routed experts in a check of M tokens, per card, from the distinct experts per (block, layer)
of an OWN_MT_IDDUMP file (consecutive tokens form a block, as dsv41_distinct_experts.py does) and each layer's expert
formats (read from a timeline's kernel names: RoutedU3<RU3IQ1S<20u>.. = gate+up, ..<9u> = down).
Bytes per expert and card: gate + up 2 x 384 rows x 5,120 columns, down 848 / 864 rows (light / pace card) x 2,304
columns, at the GGUF block sizes (256 weights per block: IQ1_S 50 B, IQ2_XXS 66, IQ2_XS 74, IQ2_S 82, Q2_K 84,
IQ3_XXS 98; the engine's packed rows are ~1 % larger, dsv41_step_budget).
usage: python3 -I floor_experts.py IDDUMP TIMELINE STEP [--bw 550] [--sizes 1,2,3,4,5,6]"""
import argparse
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from roles96 import T, classify  # noqa: E402

BLK = {'IQ1S': 50, 'IQ2XXS': 66, 'IQ2XS': 74, 'IQ2S': 82, 'Q2K': 84, 'IQ3XXS': 98}


def fmt_of(nm):
    m = re.search(r'(IQ1S|IQ2XXS|IQ2XS|IQ2S|IQ3XXS|Q2K)', nm.replace('_', ''))
    return m.group(1) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dump')
    ap.add_argument('timeline')
    ap.add_argument('step', type=int)
    ap.add_argument('--bw', type=float, default=550.0)
    ap.add_argument('--sizes', default='1,2,3,4,5,6')
    a = ap.parse_args()
    sizes = [int(x) for x in a.sizes.split(',')]
    t = T.read_timeline(a.timeline)
    gu, dn = {}, {}
    for r, x, L in classify(t, a.step, 2):
        nm = t['names'][x.nid]
        if r == 'experts gate+up':
            gu[L] = fmt_of(nm)
        elif r == 'experts down':
            dn[L] = fmt_of(nm)
    per_layer = collections.defaultdict(list)
    with open(a.dump) as f:
        for line in f:
            v = line.split()
            if len(v) < 2:
                continue
            L, M = int(v[0]), int(v[1])
            ids = [int(x) for x in v[2:]]
            for i in range(M):
                per_layer[L].append(tuple(ids[6 * i:6 * i + 6]))
    dist = collections.defaultdict(dict)  # M -> L -> mean distinct
    for L, toks in per_layer.items():
        for M in sizes:
            n = len(toks) // M
            dist[M][L] = sum(len(set(e for tk in toks[b * M:(b + 1) * M] for e in tk)) for b in range(n)) / n
    layers = sorted(gu)
    print('layers %d; gate+up formats %s; down formats %s' % (len(layers), dict(collections.Counter(gu.values())),
                                                             dict(collections.Counter(dn.values()))))
    print('%3s %8s %10s %10s %10s %10s %10s' % ('M', 'distinct', 'gu MB', 'down MB', 'floor us', 'd floor', 'd distinct'))
    prev = None
    rows = {}
    for M in sizes:
        gub = sum(dist[M][L] * 768 * 20 * BLK[gu[L]] for L in layers) / 1e6
        dnb = sum(dist[M][L] * 864 * 9 * BLK[dn[L]] for L in layers) / 1e6
        fl = (gub + dnb) * 1e6 / (a.bw * 1e3)  # us
        dmean = sum(dist[M][L] for L in layers) / len(layers)
        rows[M] = (gub, dnb, fl, dmean)
        print('%3d %8.2f %10.1f %10.1f %10.0f %10s %10s' % (M, dmean, gub, dnb, fl, '%+.0f' % (fl - prev[2]) if prev else '',
                                                            '%+.2f' % (dmean - prev[3]) if prev else ''))
        prev = rows[M]
    print('(pace card: down rows 864; floor = (gate+up + down bytes) / %.0f GB/s; gate+up and down split: '
          'gu us = MB / bw)' % a.bw)
    for M in sizes:
        gub, dnb, fl, _ = rows[M]
        print('  M=%d: gate+up %.0f us, down %.0f us' % (M, gub * 1e3 / a.bw, dnb * 1e3 / a.bw))


if __name__ == '__main__':
    main()
