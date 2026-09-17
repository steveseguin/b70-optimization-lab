#!/usr/bin/env python3
"""Summarise a torch/XPU profiler trace (Chrome trace JSON, optionally gzipped) of a decode window.

Reports, for the whole window: wall time, device kernel busy time and the idle share, kernel launches, host-side op
count, the top kernels by total device time, and, when a `ProfilerStep`/`execute_model` style host span exists, the
per-step wall and busy time. Device events are those whose category names a GPU/XPU kernel or memcpy; host events
are the rest. Nothing here touches a server.

usage: analyze-decode-trace.py trace.json[.gz] [--top 25] [--tokens N] [--out summary.json]
"""
import argparse
import collections
import gzip
import json
from pathlib import Path

DEVICE_CATS = ('kernel', 'gpu_op', 'xpu_op', 'gpu_memcpy', 'gpu_memset', 'xpu_memcpy', 'xpu_memset', 'Kernel', 'gpu_user_annotation')
STEP_NAMES = ('ProfilerStep', 'execute_model', 'GPUModelRunner.execute_model', 'Worker.execute_model')


def load(path):
    """Stream the trace's events one JSON object at a time (a 340 MB trace does not fit this host as Python objects)."""
    opener = gzip.open if str(path).endswith('.gz') else open
    decoder = json.JSONDecoder()
    with opener(path, 'rt') as handle:
        head = handle.read(1 << 16)
        start = head.find('"traceEvents"')
        start = head.find('[', start) if start >= 0 else head.find('[')
        buffer = head[start + 1:]
        while True:
            buffer = buffer.lstrip(' \n\r\t,')
            if buffer.startswith(']'):
                return
            try:
                obj, end = decoder.raw_decode(buffer)
            except json.JSONDecodeError:
                chunk = handle.read(1 << 20)
                if not chunk:
                    return
                buffer += chunk
                continue
            buffer = buffer[end:]
            if len(buffer) < 1 << 16:
                buffer += handle.read(1 << 20)
            yield obj


def busy_time(intervals):
    """Union length of [start, end) intervals in microseconds."""
    total, current_end = 0.0, None
    for start, end in sorted(intervals):
        if current_end is None or start >= current_end:
            total += end - start
            current_end = end
        elif end > current_end:
            total += end - current_end
            current_end = end
    return total


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('trace', type=Path)
    ap.add_argument('--top', type=int, default=25)
    ap.add_argument('--tokens', type=int, help='generated tokens in the window, for per-token figures')
    ap.add_argument('--out', type=Path)
    a = ap.parse_args()
    n_events = n_device = n_host = 0
    t0, t1 = None, None
    dev_intervals = []
    by_name = collections.defaultdict(lambda: [0, 0.0])
    cats = collections.Counter()
    steps = []
    for e in load(a.trace):
        if e.get('ph') != 'X' or 'dur' not in e:
            continue
        n_events += 1
        cat = str(e.get('cat', ''))
        cats[cat] += 1
        ts, dur = e['ts'], e['dur']
        t0 = ts if t0 is None else min(t0, ts); t1 = ts + dur if t1 is None else max(t1, ts + dur)
        if cat in DEVICE_CATS or 'kernel' in cat.lower():
            n_device += 1
            dev_intervals.append((ts, ts + dur))
            by_name[e['name']][0] += 1; by_name[e['name']][1] += dur
        else:
            n_host += 1
            name = e.get('name', '')
            if any(name.startswith(s) or s in name for s in STEP_NAMES):
                steps.append({'name': name, 'dur': dur})
    if not n_events:
        raise SystemExit('no complete events in trace')
    wall_us = t1 - t0
    busy_us = busy_time(dev_intervals)
    top = sorted(by_name.items(), key=lambda kv: -kv[1][1])[:a.top]
    events, device, host = range(n_events), range(n_device), range(n_host)
    summary = {
        'trace': str(a.trace), 'events': len(events), 'device_events': len(device), 'host_events': len(host), 'categories': dict(cats.most_common(12)),
        'wall_ms': wall_us / 1000, 'device_busy_ms': busy_us / 1000, 'device_idle_share': 1 - busy_us / wall_us if wall_us else None,
        'distinct_kernels': len(by_name),
        'top_kernels': [{'name': n[:120], 'count': c, 'total_ms': d / 1000, 'mean_us': d / c} for n, (c, d) in top],
        'steps': {'count': len(steps), 'mean_ms': (sum(e['dur'] for e in steps) / len(steps) / 1000) if steps else None,
                  'names': sorted({e['name'][:60] for e in steps})[:5]},
    }
    if a.tokens:
        summary['per_token'] = {'wall_ms': wall_us / 1000 / a.tokens, 'device_busy_ms': busy_us / 1000 / a.tokens,
                                'kernel_launches': len(device) / a.tokens, 'host_ops': len(host) / a.tokens}
    print(json.dumps({k: v for k, v in summary.items() if k != 'top_kernels'}, indent=1))
    for row in summary['top_kernels']:
        print(f"{row['total_ms']:9.1f} ms {row['count']:7d} x {row['mean_us']:8.1f} us  {row['name']}")
    if a.out:
        a.out.write_text(json.dumps(summary, indent=2) + '\n')


if __name__ == '__main__':
    main()
