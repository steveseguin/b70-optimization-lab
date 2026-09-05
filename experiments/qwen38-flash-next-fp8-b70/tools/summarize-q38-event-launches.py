#!/usr/bin/env python3
"""Per-launch GPU-event lines (Q38_EVENT_LAUNCHES, Q38_LAYER_TIMING_LOG>=3) -> per-site medians and cross-rank skew.
For each forward and event name, aligns the per-launch lists of the four ranks and reports, per launch index
(= layer for once-per-layer sites): median over ranks, max-min across ranks (skew), summed over launches.
    summarize-q38-event-launches.py <server.log> [--tokens 1] [--out json]
"""
from __future__ import annotations
import argparse, collections, json, re, statistics
PAT = re.compile(r"\(Worker_(TP\d)_EP\d[^)]*\).*Q38_EVENT_LAUNCHES (\S+) (.*)$")
FWD = re.compile(r"\(Worker_(TP\d)_EP\d[^)]*\).*Q38_SUBOP_TIMING forward=(\d+) tokens=(\d+)")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("server_log"); ap.add_argument("--tokens", type=int, default=1); ap.add_argument("--out")
    a = ap.parse_args()
    # events are logged right before the SUBOP line of the same forward on the same rank
    pending = collections.defaultdict(dict)   # rank -> {name: values}
    forwards = collections.defaultdict(dict)  # (fwd) -> {rank: {name: values}}
    tokens_of = {}
    for line in open(a.server_log, errors="replace"):
        m = PAT.search(line)
        if m:
            rank, name, rest = m.groups(); pending[rank][name] = [float(v) for v in rest.split()]; continue
        m = FWD.search(line)
        if m:
            rank, fwd, tok = m.group(1), int(m.group(2)), int(m.group(3))
            forwards[fwd][rank] = pending[rank]; pending[rank] = {}; tokens_of[fwd] = tok
    out = {}
    for fwd in sorted(forwards):
        if tokens_of[fwd] != a.tokens: continue
        ranks = sorted(forwards[fwd]);
        if len(ranks) < 2: continue
        names = set().union(*(forwards[fwd][r].keys() for r in ranks))
        row = {}
        for name in sorted(names):
            lists = [forwards[fwd][r].get(name) for r in ranks]
            if any(l is None for l in lists): continue
            n = min(len(l) for l in lists)
            per_launch_median = [statistics.median(l[i] for l in lists) for i in range(n)]
            per_launch_skew = [max(l[i] for l in lists) - min(l[i] for l in lists) for i in range(n)]
            row[name] = dict(launches=n, sum_median_ms=round(sum(per_launch_median), 3), sum_skew_ms=round(sum(per_launch_skew), 3),
                             per_rank_sum_ms={r: round(sum(l[:n]), 3) for r, l in zip(ranks, lists)},
                             max_launch_ms=round(max(max(l[:n]) for l in lists), 3), median_launch_ms=round(statistics.median(per_launch_median), 4))
        out[f"forward{fwd}"] = row
        print(f"forward {fwd} (tokens={tokens_of[fwd]}):")
        for name, v in row.items():
            print(f"  {name:36s} n={v['launches']:3d} sum(median over ranks)={v['sum_median_ms']:8.3f} ms  sum(max-min across ranks)={v['sum_skew_ms']:7.3f} ms  median/launch={v['median_launch_ms']:.4f}  max launch={v['max_launch_ms']:.3f}  per-rank sums={v['per_rank_sum_ms']}")
    if a.out: json.dump(out, open(a.out, "w"), indent=1)

if __name__ == "__main__":
    main()
