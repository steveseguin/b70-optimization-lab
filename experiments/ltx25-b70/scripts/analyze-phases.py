#!/usr/bin/env python3
"""Aggregate emitted_phases + stage_seconds from pipeline-sampler receipts.

Answers the packet-90 question: where does the pair wall go, and how much of
the interleave loss sits in which phase. Event elapsed_time on a stream is a
wall delta between marks (idle gaps included), so phases attribute wall time,
not occupancy - the script reports them as such.

Usage: analyze-phases.py <run-dir> <receipt-glob-prefix> [--csv]
"""
import glob
import json
import statistics
import sys
from pathlib import Path


def decode_report(run, prefix):
    """Aggregate decode_split (vae vs MP4-save seconds) from decode receipts."""
    vae, save, jobs = [], [], []
    for f in sorted(glob.glob(str(run / f'pipeline-decode-{prefix}*.json'))):
        try:
            d = json.loads(Path(f).read_text())
        except Exception:
            continue
        det = d.get('detail', {})
        split = det.get('decode_split')
        job = det.get('stage_seconds')
        if isinstance(split, dict):
            vae.append(split.get('vae_s', 0.0))
            save.append(split.get('save_s', 0.0))
        if job:
            jobs.append(job)
    if not vae:
        return
    print(f'decode split: {len(vae)} receipts - '
          f'vae mean {statistics.mean(vae):.3f}s (median {statistics.median(vae):.3f}), '
          f'save mean {statistics.mean(save):.3f}s (median {statistics.median(save):.3f}), '
          f'save share {sum(save) / max(1e-9, sum(vae) + sum(save)):.1%} of in-job time')


def busy_report(files):
    """Aggregate route_busy_ms across receipts: per-card busy vs job wall."""
    per_key = {}
    job_total = 0.0
    n = 0
    for f in files:
        try:
            d = json.loads(Path(f).read_text())
        except Exception:
            continue
        busy = d.get('route_busy_ms')
        if not isinstance(busy, dict):
            continue
        n += 1
        job = d.get('detail', {}).get('stage_seconds') or 0.0
        job_total += job
        for key, agg in busy.items():
            acc = per_key.setdefault(key, {'count': 0, 'ms': 0.0})
            acc['count'] += agg.get('count', 0)
            acc['ms'] += agg.get('ms', 0.0)
    if not n:
        return
    per_card = {}
    for key, agg in per_key.items():
        card = key.split('/')[0]
        per_card[card] = per_card.get(card, 0.0) + agg['ms']
    print(f'route_busy_ms: {n} receipts, total job wall {job_total:.1f}s')
    for card in sorted(per_card):
        busy = per_card[card] / 1000.0
        print(f'  {card}: busy {busy:8.1f}s over receipts ({busy / n:6.3f}s per receipt avg)')
    top = sorted(per_key.items(), key=lambda kv: -kv[1]['ms'])[:6]
    for key, agg in top:
        print(f'  {key:<18} {agg["count"]:>6} windows  {agg["ms"] / 1000.0:8.1f}s')
    print()



def main():
    run = Path(sys.argv[1])
    prefix = sys.argv[2]
    files = sorted(glob.glob(str(run / f'pipeline-sampler-{prefix}*.json')))
    rows = []
    for f in files:
        try:
            d = json.loads(Path(f).read_text())
        except Exception:
            continue
        det = d.get('detail', {})
        ph = det.get('emitted_phases')
        if not ph or not det.get('primed', True):
            continue
        stage_a = ph.get('concat_a->sample_a', {}).get('cpu_s')
        stage_b = ph.get('concat_b->sample_b', {}).get('cpu_s')
        upsample = ph.get('separate_a->upsample', {}).get('cpu_s')
        if stage_a is None or stage_b is None:
            continue
        rows.append({
            'receipt': Path(f).stem.replace('pipeline-sampler-', ''),
            'emitted': det.get('emitted_index'),
            'job_s': det.get('stage_seconds'),
            'stage_a': stage_a,
            'upsample': upsample,
            'stage_b': stage_b,
            'a_xpu0_ms': ph['concat_a->sample_a'].get('xpu0_ms'),
            'a_xpu1_ms': ph['concat_a->sample_a'].get('xpu1_ms'),
            'b_xpu0_ms': ph['concat_b->sample_b'].get('xpu0_ms'),
            'b_xpu1_ms': ph['concat_b->sample_b'].get('xpu1_ms'),
        })
    if not rows:
        print('no receipts with phases')
        return 1
    # Skip the first two emissions (pipeline fill) for steady-state stats.
    steady = [r for r in rows if (r['emitted'] or 0) >= 2] or rows

    def stats(key, rs=steady):
        vals = [r[key] for r in rs if r[key] is not None]
        if not vals:
            return 'n/a'
        vals.sort()
        p95 = vals[min(len(vals) - 1, int(len(vals) * 0.95))]
        return f'{statistics.mean(vals):8.4f}  {statistics.median(vals):8.4f}  {p95:8.4f}  {min(vals):8.4f}  {max(vals):8.4f}'

    print(f'receipts with phases: {len(rows)} (steady {len(steady)})')
    print(f'{"metric":<14} {"mean":>8}  {"median":>8}  {"p95":>8}  {"min":>8}  {"max":>8}')
    for key in ('job_s', 'stage_a', 'upsample', 'stage_b'):
        print(f'{key:<14} {stats(key)}')
    chain = [r['stage_a'] + (r['upsample'] or 0) + r['stage_b'] for r in steady]
    print(f'{"chain_total":<14} {statistics.mean(chain):8.4f}  {statistics.median(chain):8.4f}')
    print()
    # Derived overlap picture: per-pair wall is not in these receipts (it is
    # the campaign's inter-emission interval); what IS here is the per-job
    # time. Report the phase shares so the loss can be placed by name.
    a = statistics.mean(r['stage_a'] for r in steady)
    b = statistics.mean(r['stage_b'] for r in steady)
    u = statistics.mean(r['upsample'] or 0 for r in steady)
    j = statistics.mean(r['job_s'] for r in steady if r['job_s'])
    print(f'phase shares of the {j:.3f}s job: stage_a {a / j:.1%}, stage_b {b / j:.1%}, '
          f'upsample {u / j:.1%}, unaccounted {max(0.0, j - a - b - u) / j:.1%}')
    print(f'stage_a:stage_b ratio {a / b:.2f} (same 48-block shard; difference is steps x tokens)')
    print()
    busy_report(files)
    decode_report(run, prefix)
    if '--csv' in sys.argv:
        print()
        print('receipt,emitted,job_s,stage_a,upsample,stage_b')
        for r in rows:
            print(f"{r['receipt']},{r['emitted']},{r['job_s']},{r['stage_a']},{r['upsample']},{r['stage_b']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
