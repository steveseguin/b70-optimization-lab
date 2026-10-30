#!/usr/bin/env python3
"""Per-site device-time census from OWNRT_SITE_TRACE runs (research/decode-site-census-2026-10-30). CPU only.

  analyze.py sites RUN_DIR [--skip N] [--out results/X.json]

RUN_DIR is a census_driver.py run (summary.json + rank<r>/site-trace.jsonl). Phases are assigned to requests (modes) in
order: every request starts with the prefix's draft replay row at position 1 (rank 0) or with its first traced window phase
(rank 1, positions restart). Window phases are positions [K+skip, K+W). Per phase, every event's device duration is summed
per site label (blk.N.role); per mode the median over phases of each role's summed microseconds (all layers), its launch
count, and per-layer-kind values are reported, plus the phase span (first start to last end), busy time and gaps.
"""
import argparse, collections, json, re, statistics, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SMALL_US = 20.0
LAYER = re.compile(r'^(?:draft\.)?blk\.(\d+)\.(.*)$')


def role_of(label):
    m = LAYER.match(label)
    if m:
        return int(m.group(1)), m.group(2)
    return -1, label


def load_trace(run):
    s = json.loads((Path(run) / 'summary.json').read_text())
    rank = s['rank']
    phases, events = [], collections.defaultdict(list)
    with open(Path(run) / f'rank{rank}' / 'site-trace.jsonl') as f:
        for line in f:
            d = json.loads(line)
            if 'phase' in d:
                phases.append(d)
            else:
                events[d['p']].append((d['c'], d['k'], d['s'], d['e']))
    return s, phases, events


def assign_requests(s, phases):
    """Split phases into requests: a request starts when the position sequence restarts."""
    K, W = s['prefix'], s['window']
    groups, cur, last = [], [], None
    for ph in phases:
        pos = ph['position']
        restart = last is not None and pos < last and pos <= K  # positions only grow inside a request
        if restart:
            groups.append(cur); cur = []
        cur.append(ph); last = pos
    if cur:
        groups.append(cur)
    if len(groups) != len(s['modes']):
        raise SystemExit(f'{len(groups)} phase groups for {len(s["modes"])} modes')
    return dict(zip(s['modes'], groups))


def phase_stats(evs):
    evs = sorted(evs, key=lambda x: x[2])
    busy = sum(e - st for _, _, st, e in evs) / 1000.0
    span = (max(e for *_, e in evs) - evs[0][2]) / 1000.0
    gaps, prev = [], None
    for _, _, st, e in evs:
        if prev is not None:
            gaps.append(max(0, st - prev) / 1000.0)
        prev = max(prev or 0, e)
    return busy, span, gaps


def sites(run, skip):
    s, phases, events = load_trace(run)
    K, W = s['prefix'], s['window']
    by_mode = assign_requests(s, phases)
    out = dict(run=str(run), rank=s['rank'], binary=s['binary'], prefix=K, window=W, skip=skip, modes={})
    for mode, group in by_mode.items():
        kinds = collections.defaultdict(list)
        for ph in group:
            if K + skip <= ph['position'] < K + W and ph['phase'] in events:
                kinds[ph['kind']].append(ph)
        res = {}
        for kind, phs in kinds.items():
            per_role = collections.defaultdict(list)      # role -> per-phase summed us
            per_role_n = collections.defaultdict(list)    # role -> per-phase launch count
            per_site = collections.defaultdict(list)      # full label -> per-phase us
            per_launch = collections.defaultdict(list)    # role -> individual launch us
            spans, busys, gapsum, nevents, rows, maxgap = [], [], [], [], [], []
            small_n, small_us = [], []                    # kernels under SMALL_US per phase
            small_roles = collections.defaultdict(list)   # role -> per-phase (count, us) of its sub-SMALL_US launches
            for ph in phs:
                evs = events[ph['phase']]
                busy, span, gaps = phase_stats(evs)
                spans.append(span); busys.append(busy); gapsum.append(sum(gaps)); nevents.append(len(evs)); rows.append(ph['rows'])
                maxgap.append(max(gaps) if gaps else 0.0)
                sm = [(role_of(c)[1], (e - st) / 1000.0) for c, k, st, e in evs if (e - st) / 1000.0 < SMALL_US]
                small_n.append(len(sm)); small_us.append(sum(u for _, u in sm))
                per = collections.defaultdict(lambda: [0, 0.0])
                for r_, u in sm:
                    per[r_][0] += 1; per[r_][1] += u
                for r_ in set(per) | set(small_roles):
                    small_roles[r_].append(per.get(r_, [0, 0.0]))
                r_us, r_n, s_us = collections.Counter(), collections.Counter(), collections.Counter()
                for c, k, st, e in evs:
                    layer, role = role_of(c)
                    us = (e - st) / 1000.0
                    r_us[role] += us; r_n[role] += 1; s_us[c] += us
                    per_launch[role].append(us)
                for role in set(r_us) | set(per_role):
                    per_role[role].append(r_us.get(role, 0.0)); per_role_n[role].append(r_n.get(role, 0))
                for c, us in s_us.items():
                    per_site[c].append(us)
            med = statistics.median
            res[kind] = dict(
                phases=len(phs), rows=sorted(set(rows)),
                span_us=med(spans), busy_us=med(busys), gap_us=med(gapsum), events=med(nevents),
                span_us_mean=statistics.fmean(spans), busy_us_mean=statistics.fmean(busys),
                max_gap_us=med(maxgap), span_without_max_gap_us=med([a - b for a, b in zip(spans, maxgap)]),
                small=dict(threshold_us=SMALL_US, launches=med(small_n), us=med(small_us),
                           roles={r_: dict(launches=med([x[0] for x in v]), us=med([x[1] for x in v])) for r_, v in sorted(small_roles.items())}),
                roles={r: dict(us=med(v), us_mean=statistics.fmean(v), launches=med(per_role_n[r]),
                               launch_us_median=med(per_launch[r]) if per_launch[r] else 0.0,
                               launch_us_min=min(per_launch[r]) if per_launch[r] else 0.0)
                       for r, v in sorted(per_role.items())},
                sites={c: med(v) for c, v in sorted(per_site.items())})
        out['modes'][mode] = res
    return out


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('sites')
    p.add_argument('run')
    p.add_argument('--skip', type=int, default=8)
    p.add_argument('--out')
    a = ap.parse_args()
    if a.cmd == 'sites':
        r = sites(a.run, a.skip)
        txt = json.dumps(r, indent=1)
        if a.out:
            Path(a.out).write_text(txt)
        for mode, kinds in r['modes'].items():
            for kind, v in kinds.items():
                print(f"mode {mode:>2} {kind:<10} phases {v['phases']:>4} rows {v['rows']} span {v['span_us']:9.1f} busy {v['busy_us']:9.1f} gaps {v['gap_us']:7.1f} events {v['events']}")


if __name__ == '__main__':
    main()
