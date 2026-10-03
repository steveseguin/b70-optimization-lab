#!/usr/bin/env python3
"""Aggregate emitted_phases, route busy windows and the decode split from a run.

Answers the packet-90 questions: where does the pair wall go, how busy is
each card inside it, and how the decode job splits between VAE decode and
the MP4 preview save.

- emitted_phases: event elapsed_time between chain marks on a stream is a
  WALL delta (idle gaps included), so the first table attributes wall time
  by phase, not occupancy.
- route_busy_ms (packet 90b+): the sum of per-replay event windows per card,
  drained at each sampler receipt. Occupancy = busy / wall over the steady
  receipts, the wall taken from the receipts' own write times
  (`written_unix` when present, else file mtime).
- decode_split (packet 90b+): vae_s / save_s inside the decode job.

Receipts lacking the newer fields (f90 and earlier) are still analysed; the
sections they cannot feed are reported as absent.

Steady state is relative to the run's index base: clip `emitted - base` for
the base the runner passed (--index-base), recovered from the receipts as
`clip_index - <prompt number>` unless --base is given. The first --skip
emitted clips (default 2: the clips sampled while the pipeline filled) are
excluded from steady statistics.

Usage: analyze-phases.py <run-dir> <receipt-prefix> [--skip N] [--base B] [--csv]
  e.g. analyze-phases.py R/encoder-server-sentry-90 f90-endure
"""
import argparse
import collections
import glob
import json
import os
import re
import statistics
import sys
from pathlib import Path

PHASE_ORDER = ('start->concat_a', 'concat_a->sample_a', 'sample_a->separate_a',
               'separate_a->upsample', 'upsample->concat_b', 'concat_b->sample_b',
               'sample_b->separate_b')


def load(run, kind, prefix):
    """[(prompt_number, path, receipt)] for complete receipts of one prefix."""
    out = []
    pat = re.compile(re.escape(f'{kind}-{prefix}-') + r'(\d+)\.json$')
    for f in glob.glob(str(run / f'{kind}-{prefix}-*.json')):
        m = pat.search(f)
        if not m:
            continue
        try:
            d = json.loads(Path(f).read_text())
        except Exception:  # noqa: BLE001  (0-byte / truncated files after a freeze)
            continue
        out.append((int(m.group(1)), f, d))
    out.sort(key=lambda t: t[0])
    return out


def index_base(receipts):
    bases = collections.Counter(d['clip_index'] - n for n, _, d in receipts
                                if isinstance(d.get('clip_index'), int))
    return bases.most_common(1)[0][0] if bases else None


def written_at(path, receipt):
    t = receipt.get('written_unix')
    return float(t) if isinstance(t, (int, float)) else os.stat(path).st_mtime


def summary(vals):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return f'{"n/a":>8}'
    p95 = vals[min(len(vals) - 1, int(len(vals) * 0.95))]
    return (f'{statistics.mean(vals):8.4f}  {statistics.median(vals):8.4f}  {p95:8.4f}  '
            f'{vals[0]:8.4f}  {vals[-1]:8.4f}  n={len(vals)}')


HEADER = f'{"":<26} {"mean":>8}  {"median":>8}  {"p95":>8}  {"min":>8}  {"max":>8}'


def phase_report(rows, steady):
    print(f'sampler receipts with phases: {len(rows)} (steady {len(steady)})')
    print('wall between marks (seconds; event deltas include idle gaps):')
    print(HEADER)
    print(f'{"job_s":<26} {summary(r["job_s"] for r in steady)}')
    for name in PHASE_ORDER:
        for col, scale in (('cpu_s', 1.0), ('xpu0_ms', 1e-3), ('xpu1_ms', 1e-3)):
            vals = [r['phases'].get(name, {}).get(col) for r in steady]
            vals = [v * scale for v in vals if v is not None]
            if vals:
                label = f'{name} {col.replace("_ms", "").replace("_s", "")}'
                print(f'{label:<26} {summary(vals)}')
    chain = [r['stage_a'] + (r['upsample'] or 0) + r['stage_b'] for r in steady]
    print(f'{"chain_total cpu":<26} {summary(chain)}')
    a = statistics.mean(r['stage_a'] for r in steady)
    b = statistics.mean(r['stage_b'] for r in steady)
    u = statistics.mean(r['upsample'] or 0 for r in steady)
    jobs = [r['job_s'] for r in steady if r['job_s']]
    if jobs:
        j = statistics.mean(jobs)
        print(f'phase shares of the {j:.3f}s job: stage_a {a / j:.1%}, stage_b {b / j:.1%}, '
              f'upsample {u / j:.1%}, unaccounted {max(0.0, j - a - b - u) / j:.1%}')
    print(f'stage_a:stage_b ratio {a / b:.2f} (same 48-block shard; difference is steps x tokens)')
    print()


def busy_report(steady_receipts):
    """Per-card busy from route_busy_ms over steady receipts, against their wall.

    sum = total length of replay windows (the two sampler threads' windows
    overlap when they co-run on one card, so sum can exceed the wall);
    union = card time with at least one replay in flight (needs the 90b
    '_devices' entry); overlap = sum - union.
    """
    have = [(p, d) for p, d in steady_receipts if isinstance(d.get('route_busy_ms'), dict)]
    bad = [d.get('route_busy_ms') for _, d in steady_receipts
           if isinstance(d.get('route_busy_ms'), str)]
    if not have:
        msg = 'absent from these receipts (pre-90b packet)'
        if bad:
            msg = f'unavailable in {len(bad)} receipts, e.g. {bad[0][:120]}'
        print(f'route_busy_ms: {msg}')
        print()
        return
    times = sorted(written_at(p, d) for p, d in have)
    tot = collections.defaultdict(lambda: collections.defaultdict(float))  # card -> sum/union
    rcpt = collections.defaultdict(lambda: collections.defaultdict(list))
    per_key = collections.defaultdict(lambda: [0, 0.0])
    meta = collections.Counter()
    # Windows drained at receipt k completed between receipt k-1 and k, so
    # the first steady receipt opens the wall interval and its own windows
    # (which precede that interval) are excluded from the occupancy totals.
    first = min(range(len(have)), key=lambda i: written_at(*have[i]))
    for i, (p, d) in enumerate(have):
        busy = d['route_busy_ms']
        sums = collections.defaultdict(float)
        for key, agg in busy.items():
            if key.startswith('_'):
                continue
            sums[key.split('/')[0]] += agg.get('ms', 0.0) / 1000.0
            per_key[key][0] += agg.get('count', 0)
            per_key[key][1] += agg.get('ms', 0.0)
        meta.update({k: v for k, v in busy.get('_meta', {}).items() if isinstance(v, int)})
        unions = {card: v.get('union_ms', 0.0) / 1000.0 for card, v in busy.get('_devices', {}).items()}
        for card in set(sums) | set(unions):
            rcpt[card]['sum'].append(sums.get(card, 0.0))
            if card in unions:
                rcpt[card]['union'].append(unions[card])
            if i != first:
                tot[card]['sum'] += sums.get(card, 0.0)
                tot[card]['union'] += unions.get(card, 0.0)
    wall = times[-1] - times[0]
    per = wall / max(1, len(have) - 1)
    print(f'route_busy_ms: {len(have)} steady receipts, wall {wall:.1f}s between first and last '
          f'receipt write ({len(have) - 1} intervals, {per:.3f}s per receipt)')
    print(f'  {"card":<8} {"sum/rcpt":>9} {"occ(sum)":>9} {"union/rcpt":>11} {"occupancy":>10} {"co-run overlap":>15}')
    for card in sorted(rcpt):
        r = rcpt[card]
        occ_sum = tot[card]['sum'] / wall if wall > 0 else float('nan')
        if r['union']:
            occ = tot[card]['union'] / wall if wall > 0 else float('nan')
            overlap = tot[card]['sum'] - tot[card]['union']
            print(f'  {card:<8} {statistics.median(r["sum"]):9.3f} {occ_sum:9.1%} '
                  f'{statistics.median(r["union"]):11.3f} {occ:10.1%} {overlap / max(1e-9, tot[card]["sum"]):15.1%}')
        else:
            print(f'  {card:<8} {statistics.median(r["sum"]):9.3f} {occ_sum:9.1%} {"n/a":>11} {"n/a":>10} {"n/a":>15}')
    print('  (per-receipt columns are medians; occupancy = union / wall = card time with any replay in')
    print('   flight; occ(sum) double-counts co-running windows and can exceed 100%)')
    if meta:
        print(f'  window bookkeeping: {dict(meta)} (carried = in flight at a drain, counted later; '
              f'dropped/errors/unplaced > 0 make busy or union an undercount)')
    print('  top routes by summed window time:')
    for key, (count, ms) in sorted(per_key.items(), key=lambda kv: -kv[1][1])[:8]:
        print(f'    {key:<18} {count:>7} windows  {ms / 1000.0:8.1f}s  {ms / max(1, count):7.3f} ms/window')
    print()


def decode_report(run, prefix, base, skip):
    receipts = load(run, 'pipeline-decode', prefix)
    steady = [(f, d) for _, f, d in receipts
              if isinstance(d.get('detail', {}).get('emitted_index'), int)
              and d['detail']['emitted_index'] >= 0
              and (base is None or d['detail']['emitted_index'] - base >= skip)]
    jobs = [d['detail'].get('stage_seconds') for _, d in steady]
    print(f'decode receipts: {len(receipts)} (steady emitted {len(steady)})')
    print(HEADER)
    print(f'{"decode job_s":<26} {summary(jobs)}')
    splits = [d['detail'].get('decode_split') for _, d in steady]
    have = [s for s in splits if isinstance(s, dict) and 'vae_s' in s]
    if not have:
        print('decode_split: absent from these receipts (pre-90b packet)')
        print()
        return
    vae = [s['vae_s'] for s in have]
    save = [s.get('save_s', 0.0) for s in have]
    rest = [d['detail']['stage_seconds'] - s['vae_s'] - s.get('save_s', 0.0)
            for (_, d), s in zip(steady, splits) if isinstance(s, dict) and 'vae_s' in s
            and d['detail'].get('stage_seconds')]
    print(f'{"  vae decode (+audio)":<26} {summary(vae)}')
    print(f'{"  mp4 preview save":<26} {summary(save)}')
    print(f'{"  job - vae - save":<26} {summary(rest)}')
    print(f'decode split: {len(have)} receipts, save share '
          f'{sum(save) / max(1e-9, sum(vae) + sum(save)):.1%} of timed in-job time')
    print()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('run', type=Path)
    ap.add_argument('prefix')
    ap.add_argument('--skip', type=int, default=2)
    ap.add_argument('--base', type=int, default=None)
    ap.add_argument('--csv', action='store_true')
    args = ap.parse_args()

    receipts = load(args.run, 'pipeline-sampler', args.prefix)
    base = args.base if args.base is not None else index_base(receipts)
    print(f'run {args.run} prefix {args.prefix}: {len(receipts)} readable sampler receipts, '
          f'index base {base}, steady = emitted - base >= {args.skip}')
    rows = []
    for n, f, d in receipts:
        det = d.get('detail', {})
        ph = det.get('emitted_phases')
        if not isinstance(ph, dict) or not det.get('primed', True):
            continue
        stage_a = ph.get('concat_a->sample_a', {}).get('cpu_s')
        stage_b = ph.get('concat_b->sample_b', {}).get('cpu_s')
        if stage_a is None or stage_b is None:
            continue
        emitted = det.get('emitted_index')
        rows.append({'n': n, 'path': f, 'receipt': d, 'phases': ph,
                     'name': Path(f).stem.replace('pipeline-sampler-', ''),
                     'emitted': emitted,
                     'rel': (emitted - base) if isinstance(emitted, int) and base is not None else None,
                     'job_s': det.get('stage_seconds'), 'stage_a': stage_a,
                     'upsample': ph.get('separate_a->upsample', {}).get('cpu_s'), 'stage_b': stage_b})
    if not rows:
        print('no receipts with phases')
        return 1
    steady = [r for r in rows if r['rel'] is not None and r['rel'] >= args.skip]
    if not steady:
        print(f'no receipts past the first {args.skip} emitted clips; using all {len(rows)}')
        steady = rows
    phase_report(rows, steady)
    busy_report([(r['path'], r['receipt']) for r in steady])
    decode_report(args.run, args.prefix, base, args.skip)
    if args.csv:
        print('receipt,emitted,rel,job_s,stage_a,upsample,stage_b')
        for r in rows:
            print(f"{r['name']},{r['emitted']},{r['rel']},{r['job_s']},{r['stage_a']},"
                  f"{r['upsample']},{r['stage_b']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
