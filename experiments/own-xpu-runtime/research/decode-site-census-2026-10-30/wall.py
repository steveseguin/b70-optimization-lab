#!/usr/bin/env python3
"""Host wall time per command in the unprofiled (--timing token) census runs: decode HALF, PREFILL chunks of M rows and
DRAFT rows, window positions [K+skip, K+W) only (research/decode-site-census-2026-10-30). CPU only.
  wall.py RUN [RUN ...] --out results/token-wall.json"""
import argparse, json, statistics
from pathlib import Path
HALF, DRAFT, PREFILL = 1, 9, 15


def run_wall(run, skip):
    s = json.loads((Path(run) / 'summary.json').read_text())
    K, W = s['prefix'], s['window']
    lo, hi = K + skip, K + W
    out = dict(run=str(run), rank=s['rank'], trace=s['trace'], modes={})
    # calls are in order; requests are separated by RESET (op 11)
    req, reqs = [], []
    for c in s['calls']:
        if c[0] == 11:
            reqs.append(req); req = []
        else:
            req.append(c)
    for mode, calls in zip(s['modes'], reqs):
        half = [(e - b) / 1e6 for op, pos, n, b, e in calls if op == HALF and lo <= pos < hi]
        pre = [(e - b) / 1e6 for op, pos, n, b, e in calls if op == PREFILL and lo <= pos < hi and n <= 8]
        dr = [(e - b) / 1e6 for op, pos, n, b, e in calls if op == DRAFT and lo <= pos < hi]
        v = {}
        if half:
            v['half_ms'] = statistics.median(half); v['half_n'] = len(half)
        if pre:
            v['prefill_chunk_ms'] = statistics.median(pre); v['prefill_n'] = len(pre)
        if dr:
            v['draft_ms'] = statistics.median(dr); v['draft_n'] = len(dr)
        out['modes'][mode] = v
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('runs', nargs='+')
    ap.add_argument('--skip', type=int, default=8)
    ap.add_argument('--out')
    a = ap.parse_args()
    r = [run_wall(x, a.skip) for x in a.runs]
    print(json.dumps(r, indent=1))
    if a.out:
        Path(a.out).write_text(json.dumps(r, indent=1))
