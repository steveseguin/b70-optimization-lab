#!/usr/bin/env python3
"""Per-round guessing log (OWN_SPEC_LOG lines: the draft's confidences, then guesses k, kept n-1, draft ms, check ms, lookup flag): check and
draft cost by guess count, kept distribution, and what a cycle costs. Usage: python3 -I spec_log_stats.py LOG..."""
import sys, collections, statistics as st
for fn in sys.argv[1:]:
    rows = []
    for line in open(fn):
        f = line.split()
        if len(f) < 5: continue
        f = f[-5:] # (the draft's per-position confidences come first)
        try: rows.append((int(f[0]), int(f[1]), float(f[2]), float(f[3]), int(f[4])))
        except ValueError: continue
    if not rows: print(fn, 'no rows'); continue
    by = collections.defaultdict(list)
    for r in rows: by[r[0]].append(r)
    tok = sum(r[1] + 1 for r in rows); ms = sum(r[2] + r[3] for r in rows)
    print(f'{fn}: {len(rows)} rounds, {tok} tokens, {tok / len(rows):.2f} per round, {ms / len(rows):.2f} ms per round, '
          f'{1000 * tok / ms:.1f} tok/s (draft + check only); draft {sum(r[2] for r in rows) / len(rows):.2f} ms, '
          f'check {sum(r[3] for r in rows) / len(rows):.2f} ms per round; lookup rounds {sum(r[4] for r in rows)}')
    print('  guesses  rounds  kept-mean  kept=0  draft-ms  check-ms(median)  check-ms(mean)')
    for k in sorted(by):
        v = by[k]
        print(f'  {k:7d} {len(v):7d} {st.mean(r[1] for r in v):10.2f} {sum(r[1] == 0 for r in v):7d} '
              f'{st.mean(r[2] for r in v):9.2f} {st.median(r[3] for r in v):17.2f} {st.mean(r[3] for r in v):15.2f}')
