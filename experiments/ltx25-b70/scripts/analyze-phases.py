#!/usr/bin/env python3
"""Aggregate emitted_phases, route busy windows and the decode split from a run.

Answers the packet-90 questions: where does the pair wall go, how busy is
each card inside it, and how the decode job splits between VAE decode and
the MP4 preview save.

- emitted_phases: event elapsed_time between chain marks on a stream is a
  WALL delta (idle gaps included), so the first table attributes wall time
  by phase, not occupancy.
- route_busy_ms (packet 90c): per-replay event windows per card, emitted at
  each sampler receipt as merged busy segments on the card's own anchor
  clock. Segments from all steady receipts are merged before measuring;
  occupancy = union / (first start .. last end) on that clock. Receipts
  whose timing is unavailable (disabled, errors, unplaced) are counted and
  printed next to every occupancy figure.
- decode_split (packet 90b+): vae_s / save_s inside the decode job.

Receipts lacking the newer fields (f90 and earlier) are still analysed; the
sections they cannot feed are reported as absent.

Steady state is relative to the run's index base: clip `emitted - base` for
the base the runner passed (--index-base), recovered from the receipts as
`clip_index - <prompt number>` unless --base is given. The first --skip
emitted clips (default 2: the clips sampled while the pipeline filled) are
excluded from steady statistics. If no row is steady the script says so and
exits 2; it never falls back to the excluded rows.

Usage: analyze-phases.py <run-dir> <receipt-prefix> [--skip N] [--base B] [--csv]
  e.g. analyze-phases.py R/encoder-server-sentry-90 f90-endure
"""
import argparse
import collections
import glob
import json
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


def merge_segments(intervals):
    out = []
    for st, en in sorted(intervals):
        if out and st <= out[-1][1]:
            out[-1][1] = max(out[-1][1], en)
        else:
            out.append([st, en])
    return out


def card_occupancy(receipts):
    """Per card from the 90c '_devices' segments of the given receipts.

    Segments from ALL drains are merged on the card's anchor clock before
    measuring, so a window carried into a later drain never double-counts.
    The denominator is the same clock: first segment start to last segment
    end. Returns {card: {union_s, span_s, sum_s, gap_ms}}.
    """
    segs = collections.defaultdict(list)
    sums = collections.defaultdict(float)
    gaps = collections.defaultdict(float)
    for d in receipts:
        for card, v in d['route_busy_ms'].get('_devices', {}).items():
            segs[card].extend((float(a), float(b)) for a, b in v.get('segments', []))
            sums[card] += v.get('sum_ms', 0.0)
            gaps[card] = max(gaps[card], v.get('coalesced_gap_ms', 0.0))
    out = {}
    for card, iv in segs.items():
        if not iv:
            continue
        merged = merge_segments(iv)
        out[card] = {'union_s': sum(b - a for a, b in merged) / 1000.0,
                     'span_s': (merged[-1][1] - merged[0][0]) / 1000.0,
                     'sum_s': sums[card] / 1000.0, 'gap_ms': gaps[card]}
    return out


def timing_available(d):
    busy = d.get('route_busy_ms')
    if not isinstance(busy, dict):
        return False
    meta = busy.get('_meta', {})
    return not meta.get('disabled') and not meta.get('errors') and not meta.get('unplaced') \
        and '_devices' in busy


def busy_report(steady_receipts):
    """Per-card occupancy of the two-clip sampler from route_busy_ms.

    occupancy = union / span on the card's own clock (time with at least one
    replay in flight over first-start..last-end of the steady windows);
    overlap = (summed window time - union) / summed: the share of window time
    in which both sampler threads had a replay on the card.
    """
    n = len(steady_receipts)
    with_field = [d for _, d in steady_receipts if 'route_busy_ms' in d]
    if not with_field:
        print('route_busy_ms: absent from these receipts (pre-90b packet)')
        print()
        return
    usable = [d for d in with_field if isinstance(d['route_busy_ms'], dict)]
    unavailable = [d for d in with_field if not timing_available(d)]
    reasons = collections.Counter()
    for d in unavailable:
        busy = d['route_busy_ms']
        if not isinstance(busy, dict):
            reasons[str(busy)[:80]] += 1
        else:
            meta = busy.get('_meta', {})
            reasons[meta.get('disabled') or
                    ('errors' if meta.get('errors') else 'unplaced' if meta.get('unplaced') else 'no segments')] += 1
    tag = f'[timing unavailable in {len(unavailable)}/{n} steady receipts]'
    per_key = collections.defaultdict(lambda: [0, 0.0])
    meta = collections.Counter()
    for d in usable:
        for key, agg in d['route_busy_ms'].items():
            if not key.startswith('_'):
                per_key[key][0] += agg.get('count', 0)
                per_key[key][1] += agg.get('ms', 0.0)
        meta.update({k: v for k, v in d['route_busy_ms'].get('_meta', {}).items() if isinstance(v, int)})
    occ = card_occupancy(usable)
    print(f'route_busy_ms: {n} steady receipts {tag}')
    if reasons:
        print(f'  unavailable because: {dict(reasons)}')
    if not occ:
        print(f'  no placed busy segments: occupancy n/a {tag}')
    else:
        print(f'  {"card":<8} {"union s":>9} {"span s":>9} {"occupancy":>10} {"summed s":>9} {"co-run overlap":>15}')
        for card in sorted(occ):
            o = occ[card]
            print(f'  {card:<8} {o["union_s"]:9.1f} {o["span_s"]:9.1f} '
                  f'{o["union_s"] / max(1e-9, o["span_s"]):10.1%} {o["sum_s"]:9.1f} '
                  f'{(o["sum_s"] - o["union_s"]) / max(1e-9, o["sum_s"]):15.1%}  {tag}'
                  + (f'  (gaps <= {o["gap_ms"]} ms coalesced)' if o['gap_ms'] else ''))
    if meta:
        print(f'  window bookkeeping: {dict(meta)} (carried = in flight at a drain, reported later; '
              f'dropped/errors/unplaced > 0 make the figures an undercount)')
    if per_key:
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
    if any('slot' in s for s in have):
        # Packet 91+: the job decodes on a placement slot and hands the
        # preview to the writer thread; save time comes from the writer.
        for slot in sorted({s.get('slot') for s in have}):
            rows = [s for s in have if s.get('slot') == slot]
            print(f'{"  vae decode " + str(slot):<26} {summary(s["vae_s"] for s in rows)}')
            print(f'{"  lock wait " + str(slot):<26} {summary(s.get("wait_s") for s in rows)}')
        print(f'{"  enqueue to writer":<26} {summary(s.get("enqueue_s") for s in have)}')
        saves = [row for _, d in receipts if isinstance(d.get('preview_writer'), dict)
                 for row in d['preview_writer'].get('saves', [])
                 if base is None or row.get('index', -1) - base >= skip]
        print(f'{"  mp4 save (writer)":<26} {summary(r.get("save_s") for r in saves)}')
        print(f'{"  writer queue wait":<26} {summary(r.get("queued_s") for r in saves)}')
        failed = [r for r in saves if str(r.get('saved', '')).startswith('save-failed')]
        print(f'decode split: {len(have)} receipts; {len(saves)} writer saves, {len(failed)} failed')
        print()
        return
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
        print(f'NO STEADY ROWS: {len(rows)} receipts with phases, none with emitted - base >= {args.skip}; '
              f'no steady phase or occupancy statistics (excluded rows are never reported as steady)')
        print()
        decode_report(args.run, args.prefix, base, args.skip)
        return 2
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
