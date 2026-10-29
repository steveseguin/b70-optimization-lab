#!/usr/bin/env python3
"""Correlate a traced rank-1 harness run's per-half fault bursts with its logged allocations (research/tp/fault-ladder-2026-10-29).
CPU only.  correlate.py RUN_DIR [--threshold 150] [--json OUT]

Half i of rank1/timings.jsonl is the i-th HALF call of summary.json "calls" (CLOCK_MONOTONIC send/reply times, the same
clock as the tracer). For every half above the threshold, lists the allocations (not frees) logged inside its window."""
import argparse, glob, json, os


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('run'); ap.add_argument('--threshold', type=int, default=150); ap.add_argument('--json')
    a = ap.parse_args()
    s = json.load(open(os.path.join(a.run, 'summary.json')))
    halves = [c for c in s['calls'] if c[0] == 1]
    rows = [json.loads(l) for l in open(os.path.join(a.run, 'rank1', 'timings.jsonl'))]
    assert len(halves) == len(rows), (len(halves), len(rows))
    log = glob.glob(os.path.join(a.run, 'alloc-trace.*.log'))[0]
    ev = []
    for line in open(log):
        if line.startswith('#'):
            continue
        h, fr = line.split('|', 1)
        t, tid, kind, size, old, ptr, mf = h.split()
        ev.append((int(t), int(tid), kind, int(size), ptr, fr.split()[:3]))
    ev.sort()
    out = []
    j = 0
    for i, (c, r) in enumerate(zip(halves, rows)):
        while j < len(ev) and ev[j][0] < c[2]:
            j += 1
        k = j; inside = []
        while k < len(ev) and ev[k][0] <= c[3]:
            if ev[k][2] != 'free':
                inside.append(ev[k])
            k += 1
        f = r['process_minor_faults']
        if f > a.threshold or (i > 0 and any(x[3] >= 1 << 20 for x in inside)):
            item = dict(half=i, position=r['position'], process=f, main=r.get('thread_minor_faults'), card1=r.get('card1_thread_minor_faults'),
                        half_ms=r['half_completion_ms'], allocations=[dict(tid=x[1], kind=x[2], bytes=x[3], pages=round(x[3] / 4096, 1)) for x in inside])
            out.append(item)
            print(i, r['position'], 'faults', f, 'main', item['main'], 'card1', item['card1'], 'allocs',
                  [(x[1], x[2], x[3], round(x[3] / 24)) for x in inside if x[3] >= 262144])
    if a.json:
        json.dump(dict(run=a.run, threshold=a.threshold, halves=len(rows), bursts=out), open(a.json, 'w'), indent=1)


if __name__ == '__main__':
    main()
