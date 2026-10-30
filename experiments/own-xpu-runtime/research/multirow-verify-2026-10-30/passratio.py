#!/usr/bin/env python3
"""Whole-pass M-row ratio from an analyze.py sites JSON (research/multirow-verify-2026-10-30). CPU only.
  passratio.py SITES.json [--wall TOKEN_RUN_SUMMARY_DIR]
Device: median span of an M-row chunk over the median span of a one-row decode half, rank 1 without its head (the
batched path skips the head; a multi-row verify adds one) and without the profiled-mode export drain. Wall (optional,
from an unprofiled run): median PREFILL call wall over median HALF call wall."""
import argparse, json, statistics
from pathlib import Path
HEAD = ('final.norm', 'final.low', 'final.gate', 'final.mix', 'final.act', 'final.inject', 'logits', 'argmax')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('sites')
    ap.add_argument('--wall')
    ap.add_argument('--out')
    a = ap.parse_args()
    s = json.loads(Path(a.sites).read_text())
    d = s['modes']['d']['half']
    head = sum(d['roles'].get(r, {}).get('us', 0.0) for r in HEAD)
    one = (d['span_without_max_gap_us'] if s['rank'] == 1 else d['span_us']) - head
    out = dict(rank=s['rank'], run=s['run'], one_row_us=one, head_us=head, modes={})
    for m, v in s['modes'].items():
        if m == 'd' or 'prefill' not in v:
            continue
        span = v['prefill']['span_us']
        out['modes'][m] = dict(span_us=span, ratio=span / one, per_row=span / one / int(m), busy_us=v['prefill']['busy_us'])
    if a.wall:
        w = json.loads((Path(a.wall) / 'summary.json').read_text())
        K, W = w['prefix'], w['window']
        reqs, cur = [], []
        for c in w['calls']:
            if c[0] == 11:
                reqs.append(cur); cur = []
            else:
                cur.append(c)
        walls = {}
        for mode, calls in zip(w['modes'], reqs):
            if mode == 'd':
                walls['d'] = statistics.median([(e - b) / 1e6 for op, pos, n, b, e in calls if op == 1 and K + 8 <= pos < K + W])
            else:
                walls[mode] = statistics.median([(e - b) / 1e6 for op, pos, n, b, e in calls if op == 15 and K + 8 <= pos < K + W and n <= 8])
        out['wall_ms'] = walls
        for m in out['modes']:
            if m in walls and 'd' in walls:
                out['modes'][m]['wall_ratio_vs_half'] = walls[m] / walls['d']
    print(json.dumps(out, indent=1))
    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
