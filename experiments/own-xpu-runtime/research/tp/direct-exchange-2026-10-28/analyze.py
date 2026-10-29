#!/usr/bin/env python3
"""Summarise the 2026-10-28 direct-exchange TP arms: per-half medians (halves 3..N, as on 2026-10-25), host enqueue
time per half (timings.jsonl enqueue_loop_ms, host waits excluded), exchange wait statistics, and the bitwise
comparison of every arm's dumped state against the one-card reference.

  analyze.py RUNS_DIR REFERENCE_ARM ARM... [--out results.json]
"""
import argparse, json, statistics, subprocess, sys
from pathlib import Path

DRIVER = Path(__file__).resolve().parents[3] / 'engine' / 'tools' / 'tp_rank1_driver.py'
IGNORE = '.expsact,.expsgate,.expsup,.routes,.routes.down'  # per-slot intermediates of slots the other card computes


def median(xs):
    return statistics.median(xs) if xs else None


def arm(runs, name, ref):
    d = runs / name
    s = json.loads((d / 'summary.json').read_text())
    half = s['half_ms']
    t = [json.loads(l) for l in (d / 'rank1' / 'timings.jsonl').read_text().splitlines() if l.strip()]
    row = dict(arm=name, binary=s.get('binary'), tp=s['tp'], split=s.get('split'), tp_env=s.get('tp_env', {}),
               steps=s['steps'], load_s=round(s['load_s'], 1), tokens=s['tokens'],
               half_ms_median_3_on=round(median(half[2:]), 3), half_ms_min_3_on=round(min(half[2:]), 3),
               half_ms_max_3_on=round(max(half[2:]), 3), half_ms=[round(x, 3) for x in half],
               engine_half_ms_median_3_on=round(median([x['half_completion_ms'] for x in t[2:]]), 3),
               enqueue_ms_median_3_on=round(median([x['enqueue_loop_ms'] for x in t[2:]]), 3),
               card0_launches_per_half=t[-1].get('launches_issued'))
    x = d / 'rank1' / 'tp-exchange.json'
    if x.exists():
        row['exchange'] = json.loads(x.read_text())
    c = d / 'rank1' / 'tp-replicate-compare.json'
    if c.exists():
        cc = json.loads(c.read_text())
        row['card1_vs_card0'] = dict(buffers=cc['buffers'], differ=len(cc['differ']),
                                     differ_outside_masked=[k for k in cc['differ'] if not any(k.endswith(i) for i in IGNORE.split(','))])
    if name != ref:
        args = [sys.executable, '-B', str(DRIVER), 'compare', str(runs / ref), str(d)]
        if s['tp'] and s.get('tp_env', {}).get('OWNRT_TP_EXPERTS'):
            args += ['--ignore', IGNORE]
        p = subprocess.run(args, capture_output=True, text=True)
        row['vs_reference'] = dict(reference=ref, rc=p.returncode, **json.loads(p.stdout))
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('runs')
    ap.add_argument('reference')
    ap.add_argument('arms', nargs='+')
    ap.add_argument('--out')
    a = ap.parse_args()
    runs = Path(a.runs)
    rows = [arm(runs, n, a.reference) for n in a.arms]
    ref = next(r for r in rows if r['arm'] == a.reference)['half_ms_median_3_on']
    for r in rows:
        r['speedup_vs_reference'] = round(ref / r['half_ms_median_3_on'], 4)
        ex = r.get('exchange', {}).get('cards')
        exs = '' if not ex else ' waits(c0/c1 polled) %d/%d of %d, max polls %d/%d, timeouts %d' % (
            ex[0]['waits_that_polled'], ex[1]['waits_that_polled'], ex[0]['waits'], ex[0]['max_polls'], ex[1]['max_polls'],
            ex[0]['timeouts'] + ex[1]['timeouts'])
        vs = r.get('vs_reference')
        vss = '' if not vs else ' | vs %s: %d compared, %d ignored, %d differ' % (vs['reference'], vs['compared'], vs['ignored'], vs['differ_count'])
        print('%-10s half %.3f ms (x%.3f) enqueue %.3f ms tokens-equal %s%s%s' % (
            r['arm'], r['half_ms_median_3_on'], r['speedup_vs_reference'], r['enqueue_ms_median_3_on'],
            r['tokens'] == rows[0]['tokens'], vss, exs))
    if a.out:
        Path(a.out).write_text(json.dumps(rows, indent=1) + '\n')


if __name__ == '__main__':
    main()
