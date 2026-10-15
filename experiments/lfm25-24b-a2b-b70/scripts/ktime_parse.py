#!/usr/bin/env python3
"""Per-token GPU time per kernel from two ktime shim outputs (-n A and -n B tokens): (B - A) / (B - A tokens).
  ktime_parse.py ktime-n16.tsv 16 ktime-n48.tsv 48"""
import collections
import subprocess
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from census_parse import short  # noqa: E402


def load(path):
    d = {}
    for line in open(path):
        name, n, ns, gap = line.rstrip("\n").split("\t")
        d[name] = (int(n), int(ns), int(gap))
    return d


def main():
    a, na, b, nb = load(sys.argv[1]), int(sys.argv[2]), load(sys.argv[3]), int(sys.argv[4])
    toks = nb - na
    names = sorted(set(a) | set(b))
    try:
        pretty = subprocess.run(["c++filt"], input="\n".join(names), capture_output=True, text=True).stdout.splitlines()
    except Exception:
        pretty = names
    g = collections.defaultdict(lambda: [0.0, 0.0, 0.0])
    for name, p in zip(names, pretty):
        za, zb = a.get(name, (0, 0, 0)), b.get(name, (0, 0, 0))
        k = short(p)
        g[k][0] += (zb[0] - za[0]) / toks
        g[k][1] += (zb[1] - za[1]) / toks / 1000.0
        g[k][2] += (zb[2] - za[2]) / toks / 1000.0
    tot_n = sum(v[0] for v in g.values())
    tot_us = sum(v[1] for v in g.values())
    tot_gap = sum(v[2] for v in g.values())
    print(f"per token: {tot_n:.1f} kernels, {tot_us:.1f} us busy, {tot_gap:.1f} us gaps (<200 us), "
          f"{tot_us + tot_gap:.1f} us total")
    print(f"{'n/tok':>7} {'us/tok':>8} {'us/call':>8} {'gap/tok':>8}  kernel")
    for k, v in sorted(g.items(), key=lambda kv: -kv[1][1]):
        if abs(v[0]) < 0.05:
            continue
        print(f"{v[0]:7.1f} {v[1]:8.1f} {v[1] / v[0] if v[0] else 0:8.2f} {v[2]:8.1f}  {k}")


if __name__ == "__main__":
    main()
