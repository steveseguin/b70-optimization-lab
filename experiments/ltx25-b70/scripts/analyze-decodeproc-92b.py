#!/usr/bin/env python3
"""Packet 92b verdict: does decode in its own process make the other stages faster?

Per arm (f92b-ctl: in-process decode on xpu:3; f92b-child: decode child on
xpu:3): exactness, stream interval median/mean, sampler / encode / decode job
medians, front-end lane CPU-s per wall-s (and busiest thread), the decode
child's CPU-s per wall-s, lock-wait median; then the preregistered rule:

  CONTINUE the split if, with both arms all-exact, the child arm's sampler AND
  encode job medians are each at least 8 % lower than the control's;
  STOP if neither improves by 8 %; otherwise MIXED.

Usage: analyze-decodeproc-92b.py <run-dir> <data-dir> [--tag f92b]
"""
import argparse
import importlib.util
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('analyze_gil_92a', HERE / 'analyze-gil-92a.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

GAIN = 0.08


def child_cpu(run, prefix):
    """Decode child CPU-s per wall-s from the emitted clips' decode splits."""
    rows = []
    for _n, d in base.load(run, 'pipeline-decode', prefix):
        split = d.get('detail', {}).get('decode_split')
        if isinstance(split, dict) and split.get('child_process_cpu_s') is not None \
                and split.get('child_wall_unix') is not None:
            rows.append((split['child_wall_unix'], split['child_process_cpu_s']))
    rows.sort()
    if len(rows) < 2 or rows[-1][0] <= rows[0][0]:
        return None
    return (rows[-1][1] - rows[0][1]) / (rows[-1][0] - rows[0][0])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('run', type=Path)
    ap.add_argument('data', type=Path)
    ap.add_argument('--tag', default='f92b')
    a = ap.parse_args()
    fmt = base.fmt
    arms = {}
    print(f'{"arm":<6} {"exact":>10} {"int med":>8} {"int mean":>8} {"sampler":>8} {"encode":>8} {"decode":>8} '
          f'{"feCPU":>7} {"maxThr":>7} {"childCPU":>8} {"lag med":>8}')
    for arm in ('ctl', 'child'):
        st = base.arm_stats(a.run, a.data, f'{a.tag}-{arm}')
        st['child_cpu'] = child_cpu(a.run, f'{a.tag}-{arm}')
        arms[arm] = st
        ex = 'n/a' if st['exact'] is None else f'{st["exact"][0]}/{st["exact"][1]}'
        print(f'{arm:<6} {ex:>10} {fmt(st["interval_median"]):>8} {fmt(st["interval_mean"]):>8} '
              f'{fmt(st["sampler_job"]):>8} {fmt(st["encode_job"]):>8} {fmt(st["decode_job"]):>8} '
              f'{fmt(st["lane_cpu"]):>7} {fmt(st["max_thread"]):>7} {fmt(st["child_cpu"]):>8} '
              f'{fmt(st["lag_median_ms"]):>8}')
    print('  (seconds; feCPU = front-end lane threads CPU-s per wall-s; childCPU = decode child process '
          'CPU-s per wall-s; lag in ms)')
    c, k = arms['ctl'], arms['child']
    exact = bool(c['exact'] and c['exact'][0] is True and k['exact'] and k['exact'][0] is True)
    gains = {}
    for key in ('sampler_job', 'encode_job'):
        gains[key] = None if None in (c[key], k[key]) or not c[key] else (c[key] - k[key]) / c[key]
    print(f'rule: both arms all-exact -> {exact}; child faster than control by >= {GAIN:.0%} in '
          f'sampler {fmt(gains["sampler_job"], ".1%")} and encode {fmt(gains["encode_job"], ".1%")}')
    if not exact or None in gains.values():
        verdict = 'INDETERMINATE (an arm is missing or not all-exact)'
    elif all(g >= GAIN for g in gains.values()):
        verdict = 'CONTINUE: per-process runtime state is a shared resource worth splitting'
    elif all(g < GAIN for g in gains.values()):
        verdict = 'STOP: moving decode out did not speed up the other stages'
    else:
        verdict = 'MIXED: one stage improved by 8 %, the other did not'
    print('verdict:', verdict)
    return 0


if __name__ == '__main__':
    sys.exit(main())
