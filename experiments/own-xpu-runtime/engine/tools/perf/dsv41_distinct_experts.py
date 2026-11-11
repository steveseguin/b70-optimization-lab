#!/usr/bin/env python3
"""Distinct routed experts per block of M prompt tokens, from an OWN_MT_IDDUMP file (prefill plan step 0).

  python3 -I dsv41_distinct_experts.py IDS_PER_LAYER.txt [--experts 384] [--topk 6] [--sizes 16,32,...]

Input lines (backend_sycl_v41_mt.inc, OWN_MT_IDSTAT=1 OWN_MT_IDDUMP=<file>, card 0): "L M id0 id1 ... id(6M-1)",
one per (block, layer), the ids of the block's tokens in token order (token t's six at 6t .. 6t + 5). A token's ids do
not depend on the block size (the traces of blocks of 16 / 5 / 1 tokens are byte-identical), so one dump at blocks of
16 gives every token's picks, and blocks of any size M are formed offline from consecutive tokens.

Prints, per M: the mean distinct experts per (block, layer), as a share of the picks (6M) and of all experts, the
uniform-random expectation E[u] = n (1 - (1 - k/n)^M) for comparison, the spread over layers (min / max of the
per-layer means), and the expert-weight bytes a block reads relative to the one-token steps (distinct / (6 M)).
Only full blocks count (the last partial block of each layer is dropped).
"""
import argparse
import collections
import statistics
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--experts", type=int, default=384)
    ap.add_argument("--topk", type=int, default=6)
    ap.add_argument("--sizes", default="1,2,4,5,8,16,32,64,128,256,512,1024")
    a = ap.parse_args()
    per_layer = collections.defaultdict(list)  # layer -> list of per-token tuples of ids
    nlines = 0
    with open(a.dump) as f:
        for line in f:
            v = line.split()
            if len(v) < 2:
                continue
            L, M = int(v[0]), int(v[1])
            ids = [int(x) for x in v[2:]]
            if len(ids) != a.topk * M:
                sys.exit(f"line {nlines + 1}: {len(ids)} ids for M = {M}")
            for t in range(M):
                per_layer[L].append(tuple(ids[a.topk * t: a.topk * (t + 1)]))
            nlines += 1
    if not per_layer:
        sys.exit("no records")
    ntok = {L: len(v) for L, v in per_layer.items()}
    print(f"{a.dump}: {nlines} (block, layer) records, {len(per_layer)} layers, tokens per layer "
          f"{min(ntok.values())}-{max(ntok.values())}")
    n, k = a.experts, a.topk
    print(f"{'M':>5} {'blocks':>7} {'distinct':>9} {'of picks':>9} {'of all':>7} {'uniform':>8} "
          f"{'layer min':>9} {'layer max':>9} {'bytes vs 1-token':>17}")
    for M in [int(x) for x in a.sizes.split(",")]:
        lay_means, allu, nb = [], [], 0
        for L, toks in sorted(per_layer.items()):
            us = []
            for b0 in range(0, len(toks) - M + 1, M):
                s = set()
                for t in toks[b0:b0 + M]:
                    s.update(t)
                us.append(len(s))
            if us:
                lay_means.append(statistics.mean(us))
                allu += us
                nb += len(us)
        if not allu:
            continue
        u = statistics.mean(allu)
        uni = n * (1 - (1 - k / n) ** M)
        print(f"{M:>5} {nb:>7} {u:>9.1f} {u / (k * M):>9.3f} {u / n:>7.3f} {uni:>8.1f} "
              f"{min(lay_means):>9.1f} {max(lay_means):>9.1f} {u / (k * M):>17.3f}")


if __name__ == "__main__":
    main()
