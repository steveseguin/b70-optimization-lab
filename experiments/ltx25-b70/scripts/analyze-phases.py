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
    if '--csv' in sys.argv:
        print()
        print('receipt,emitted,job_s,stage_a,upsample,stage_b')
        for r in rows:
            print(f"{r['receipt']},{r['emitted']},{r['job_s']},{r['stage_a']},{r['upsample']},{r['stage_b']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
