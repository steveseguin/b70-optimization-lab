#!/usr/bin/env python3
"""Packet 92a verdict: is the pipeline bound by its shared interpreter?

Per arm (switch interval 5 / 1 / 20 / 5 ms): stream interval, sampler /
encode / decode job medians, lane-thread CPU-seconds per wall-second (sum and
the busiest single thread, from /proc per-thread CPU snapshots in the sampler
receipts), lock-wait probe median/p95, the probe's own CPU cost; then the
preregistered verdict (notes/2026-10-03-process-split-design.md, section 1).

Usage: analyze-gil-92a.py <run-dir> <data-dir> [--tag f92a]
"""
import argparse
import glob
import json
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ltx_gil_probe import percentile_us  # noqa: E402

ARMS = (('s05a', 5.0), ('s01', 1.0), ('s20', 20.0), ('s05b', 5.0))
# Preregistered thresholds (design note, section 1).
CONFIRM_CPU = 0.85          # lane CPU-s per wall-s, each default arm, at least
SINGLE_THREAD_MAX = 1.0     # no single thread above (sanity)
CONFIRM_LAG_MS = 1.0        # lock-wait median, each default arm, at least
IDLE_LAG_MS = 0.2           # idle-baseline lock-wait median, below
CONFIRM_SHIFT = 0.08        # sampler or decode job median moves 1 ms vs 20 ms, at least
REFUTE_CPU = 0.6            # each default arm, at most
REFUTE_LAG_MS = 0.3         # each default arm, below
REFUTE_SHIFT = 0.03         # sampler and decode job medians 1 vs 20 ms, within


def load(run, kind, prefix):
    out = []
    pat = re.compile(re.escape(f'{kind}-{prefix}-') + r'(\d+)\.json$')
    for f in glob.glob(str(run / f'{kind}-{prefix}-*.json')):
        m = pat.search(f)
        if not m:
            continue
        try:
            out.append((int(m.group(1)), json.loads(Path(f).read_text())))
        except Exception:  # noqa: BLE001  (0-byte files after a freeze)
            continue
    return sorted(out, key=lambda t: t[0])


def med(vals):
    vals = [v for v in vals if isinstance(v, (int, float))]
    return statistics.median(vals) if vals else None


def lane(name):
    return (name.startswith('ltx-') and name != 'ltx-gil-probe') or name.startswith('lane-prompt:')


def cpu_rates(snapshots):
    """(sum of lane CPU-s per wall-s, busiest lane thread rate, its name, probe rate) between first and last."""
    snaps = [s for s in snapshots if isinstance(s, dict) and 'threads' in s]
    if len(snaps) < 2:
        return None
    a, b = snaps[0], snaps[-1]
    wall = b['wall_unix'] - a['wall_unix']
    if wall <= 0:
        return None
    total, best, best_name, probe = 0.0, 0.0, None, 0.0
    for tid, row in b['threads'].items():
        prev = a['threads'].get(tid)
        if prev is None or prev['name'] != row['name']:
            continue
        rate = (row['cpu_s'] - prev['cpu_s']) / wall
        if row['name'] == 'ltx-gil-probe':
            probe = rate
        elif lane(row['name']):
            total += rate
            if rate > best:
                best, best_name = rate, row['name']
    return total, best, best_name, probe, wall


def merge_counts(lags):
    counts = None
    for lag in lags:
        if not isinstance(lag, dict) or 'counts' not in lag:
            continue
        counts = list(lag['counts']) if counts is None else [x + y for x, y in zip(counts, lag['counts'])]
    return counts


def arm_stats(run, data, prefix):
    sampler = load(run, 'pipeline-sampler', prefix)
    decode = load(run, 'pipeline-decode', prefix)
    encode = load(run, 'pipeline', prefix)
    base = None
    if sampler:
        bases = [d['clip_index'] - n for n, d in sampler if isinstance(d.get('clip_index'), int)]
        base = statistics.mode(bases) if bases else None

    def steady(rows):
        return [d for _, d in rows if isinstance(d.get('detail', {}).get('emitted_index'), int)
                and d['detail']['emitted_index'] >= 0 and base is not None
                and d['detail']['emitted_index'] - base >= 2]
    gil = [d.get('gil') for _, d in sampler if isinstance(d.get('gil'), dict)]
    rates = cpu_rates([g.get('cpu') for g in gil])
    counts = merge_counts([g.get('lag') for g in gil[1:]])   # first drain spans the inter-arm gap
    switch = sorted({g.get('switch_interval_s') for g in gil})
    tp = data / f'{prefix}-throughput.json'
    intervals = []
    exact = None
    if tp.is_file():
        summary = json.loads(tp.read_text())
        intervals = summary.get('intervals_between_distinct_clips_s', [])[1:]
        exact = (summary.get('all_exact'), summary.get('distinct_clips_emitted'))
    return {
        'prefix': prefix, 'receipts': len(sampler), 'switch_interval_s': switch, 'exact': exact,
        'interval_median': med(intervals), 'interval_mean': statistics.mean(intervals) if intervals else None,
        'sampler_job': med([d['detail'].get('stage_seconds') for d in steady(sampler)]),
        'decode_job': med([d['detail'].get('stage_seconds') for d in steady(decode)]),
        'encode_job': med([d.get('detail', {}).get('stage_seconds') for _, d in encode[2:]]),
        'lane_cpu': None if rates is None else rates[0], 'max_thread': None if rates is None else rates[1],
        'max_thread_name': None if rates is None else rates[2], 'probe_cpu': None if rates is None else rates[3],
        'cpu_wall_s': None if rates is None else rates[4],
        'lag_median_ms': to_ms(percentile_us(counts, 0.5)) if counts else None,
        'lag_p95_ms': to_ms(percentile_us(counts, 0.95)) if counts else None,
        'lag_samples': 0 if counts is None else sum(counts),
    }


def to_ms(us):
    """Microseconds to milliseconds, None-safe (an empty histogram has no percentile)."""
    return None if us is None else us / 1000.0


def fmt(v, spec='.3f'):
    return 'n/a' if v is None else format(v, spec)


def verdict(arms, idle_ms):
    by = {a['arm']: a for a in arms}
    defaults = [by.get('s05a'), by.get('s05b')]
    lines = []
    needed = defaults + [by.get('s01'), by.get('s20')]
    if any(a is None or a.get('receipts', 1) == 0 or a['lane_cpu'] is None or a['lag_median_ms'] is None
           or a['max_thread'] is None for a in needed):
        missing = [n for n, a in zip(('s05a', 's05b', 's01', 's20'), needed)
                   if a is None or a.get('receipts', 1) == 0 or a['lane_cpu'] is None]
        return 'INDETERMINATE (missing arms or instruments: %s)' % ', '.join(missing), lines
    ref = {k: med([a[k] for a in defaults]) for k in ('sampler_job', 'decode_job')}
    shifts = {}
    for k in ('sampler_job', 'decode_job'):
        lo, hi = by['s01'][k], by['s20'][k]
        shifts[k] = None if None in (lo, hi, ref[k]) else abs(hi - lo) / ref[k]
    cpu_ok = all(a['lane_cpu'] >= CONFIRM_CPU for a in defaults)
    single_ok = all(a['max_thread'] <= SINGLE_THREAD_MAX + 0.02 for a in defaults)
    lag_ok = all(a['lag_median_ms'] >= CONFIRM_LAG_MS for a in defaults)
    idle_ok = idle_ms is not None and idle_ms < IDLE_LAG_MS
    shift_ok = any(v is not None and v >= CONFIRM_SHIFT for v in shifts.values())
    lines.append(f'  confirm: lane CPU >= {CONFIRM_CPU} in both 5 ms arms: '
                 f'{[fmt(a["lane_cpu"]) for a in defaults]} -> {cpu_ok}')
    lines.append(f'  confirm: no single thread > {SINGLE_THREAD_MAX}: '
                 f'{[fmt(a["max_thread"]) for a in defaults]} -> {single_ok}')
    lines.append(f'  confirm: lock-wait median >= {CONFIRM_LAG_MS} ms in both 5 ms arms: '
                 f'{[fmt(a["lag_median_ms"]) for a in defaults]} -> {lag_ok}')
    lines.append(f'  confirm: idle lock-wait median < {IDLE_LAG_MS} ms: {fmt(idle_ms)} -> {idle_ok}')
    lines.append(f'  confirm: sampler or decode job shifts >= {CONFIRM_SHIFT:.0%} between 1 and 20 ms: '
                 f'{ {k: fmt(v, ".1%") for k, v in shifts.items()} } -> {shift_ok}')
    refute_cpu = all(a['lane_cpu'] <= REFUTE_CPU for a in defaults)
    refute_lag = all(a['lag_median_ms'] < REFUTE_LAG_MS for a in defaults)
    refute_shift = all(v is not None and v <= REFUTE_SHIFT for v in shifts.values())
    lines.append(f'  refute: lane CPU <= {REFUTE_CPU} -> {refute_cpu}; lock-wait median < {REFUTE_LAG_MS} ms '
                 f'-> {refute_lag}; both shifts <= {REFUTE_SHIFT:.0%} -> {refute_shift}')
    if cpu_ok and single_ok and lag_ok and idle_ok and shift_ok:
        return 'CONFIRMED: the shared interpreter bounds the pipeline', lines
    if refute_cpu and refute_lag and refute_shift:
        return 'REFUTED: not the interpreter; look at card/driver contention', lines
    return 'INDETERMINATE: go to 92b (decode in a child process) as the end-to-end test', lines


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('run', type=Path)
    ap.add_argument('data', type=Path)
    ap.add_argument('--tag', default='f92a')
    a = ap.parse_args()
    idle = None
    idle_file = a.run / f'scheduler-knob-{a.tag}-idle.json'
    if idle_file.is_file():
        lag = json.loads(idle_file.read_text()).get('gil', {}).get('lag', {})
        if lag.get('counts'):
            idle = to_ms(percentile_us(lag['counts'], 0.5))
            print(f'idle baseline: {sum(lag["counts"])} probe samples, lock-wait median {fmt(idle)} ms, '
                  f'p95 {fmt(to_ms(percentile_us(lag["counts"], 0.95)))} ms')
    else:
        print('idle baseline: receipt missing')
    arms = []
    print(f'{"arm":<6} {"ms":>4} {"exact":>10} {"int med":>8} {"int mean":>8} {"sampler":>8} {"encode":>8} '
          f'{"decode":>8} {"laneCPU":>8} {"maxThr":>7} {"lag med":>8} {"lag p95":>8} {"probeCPU":>8}')
    for arm, ms in ARMS:
        st = arm_stats(a.run, a.data, f'{a.tag}-{arm}')
        st['arm'] = arm
        arms.append(st)
        ex = 'n/a' if st['exact'] is None else f'{st["exact"][0]}/{st["exact"][1]}'
        print(f'{arm:<6} {ms:>4.0f} {ex:>10} {fmt(st["interval_median"]):>8} {fmt(st["interval_mean"]):>8} '
              f'{fmt(st["sampler_job"]):>8} {fmt(st["encode_job"]):>8} {fmt(st["decode_job"]):>8} '
              f'{fmt(st["lane_cpu"]):>8} {fmt(st["max_thread"]):>7} {fmt(st["lag_median_ms"]):>8} '
              f'{fmt(st["lag_p95_ms"]):>8} {fmt(st["probe_cpu"], ".4f"):>8}')
        if st['switch_interval_s'] and st['switch_interval_s'] != [ms / 1000.0]:
            print(f'  WARNING: receipts report switch interval {st["switch_interval_s"]}, expected {ms / 1000.0}')
    print('  (seconds; laneCPU = CPU-s per wall-s summed over ltx-* worker threads and the prompt thread; '
          'maxThr = busiest single lane thread; lag in ms; probeCPU = the probe thread\'s own CPU-s per wall-s)')
    result, lines = verdict(arms, idle)
    print('verdict:', result)
    for line in lines:
        print(line)
    return 0


if __name__ == '__main__':
    sys.exit(main())
