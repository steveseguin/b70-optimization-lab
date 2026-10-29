#!/usr/bin/env python3
"""Per-half host page faults by thread (research/tp/persistent-thread-2026-10-29). Reads the per-half rows of
rank<r>/timings.jsonl (binary 1c667aea0690 and later write thread_minor_faults for the half's own thread and
card1_thread_* for card 1's submission thread) and splits each half's process faults (getrusage RUSAGE_SELF over the
half) into: main = the half's thread (RUSAGE_THREAD, same window), card1 = card 1's submission thread over its issue
loop, other = process - main - card1 (thread start/exit outside the loop, driver threads).

  faults.py runs RUNS_DIR NAME...            rank-harness run directories (decode halves: position >= prompt + 2)
  faults.py rows LABEL=FILE[,FILE...] ...    any timings.jsonl files (service requests; fixture > 0 halves)
Prints one JSON object: per label, counts, sums, medians and maxima of each class, and the half times."""
import json, statistics as st, sys
from pathlib import Path


def summarize(rows):
    out = dict(halves=len(rows))
    if not rows:
        return out
    cols = dict(process=[r['process_minor_faults'] for r in rows], main=[r.get('thread_minor_faults') for r in rows],
                card1=[r.get('card1_thread_minor_faults', 0) for r in rows],
                process_major=[r['process_major_faults'] for r in rows], main_major=[r.get('thread_major_faults') for r in rows],
                card1_major=[r.get('card1_thread_major_faults', 0) for r in rows])
    if all(v is not None for v in cols['main']):
        cols['other'] = [p - m - c for p, m, c in zip(cols['process'], cols['main'], cols['card1'])]
    for k, v in cols.items():
        if any(x is None for x in v):
            out[k] = None
            continue
        out[k] = dict(sum=sum(v), median=st.median(v), max=max(v), halves_nonzero=sum(1 for x in v if x))
    h = [r['half_completion_ms'] for r in rows]
    out['half_ms'] = dict(median=round(st.median(h), 4), max=round(max(h), 4), p90=round(sorted(h)[len(h) * 9 // 10], 4))
    s = [r['card1_thread_start_us'] for r in rows if 'card1_thread_start_us' in r]
    if s:
        out['card1_start_us'] = dict(median=round(st.median(s), 2), max=round(max(s), 2), p90=round(sorted(s)[len(s) * 9 // 10], 2))
    p = {r.get('card1_thread_persistent') for r in rows}
    out['card1_thread_persistent'] = sorted(p, key=str) if len(p) > 1 else next(iter(p))
    return out


def half_rows(path, keep):
    rows = []
    for line in open(path):
        if '"half_completion_ms"' not in line:
            continue
        r = json.loads(line)
        if keep(r):
            rows.append(r)
    return rows


if __name__ == '__main__':
    out = {}
    if sys.argv[1] == 'runs':
        runs = Path(sys.argv[2])
        for name in sys.argv[3:]:
            d = runs / name
            s = json.loads((d / 'summary.json').read_text())
            rank = '0' if (d / 'rank0').exists() else '1'
            first = s['prompt'] + 2
            rows = half_rows(d / f'rank{rank}/timings.jsonl', lambda r: r['position'] >= first)
            out[name] = dict(rank=int(rank), all=summarize(rows),
                             speculative=summarize([r for r in rows if r['speculative']]),
                             confirmed=summarize([r for r in rows if not r['speculative']]))
            if rank == '0':
                out[name]['speculative_completed'] = summarize([r for r in rows if r['speculative'] and not r['cancelled']])
    else:
        for arg in sys.argv[2:]:
            label, files = arg.split('=', 1)
            rows = []
            for f in files.split(','):
                rows += half_rows(f, lambda r: r['fixture'] > 0)
            out[label] = summarize(rows)
    print(json.dumps(out, indent=1))
