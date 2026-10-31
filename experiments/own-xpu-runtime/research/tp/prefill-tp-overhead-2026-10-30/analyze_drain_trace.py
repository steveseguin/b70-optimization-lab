#!/usr/bin/env python3
"""Card balance and host turnaround at the drains of TP batched prefill (research/tp/prefill-tp-overhead-2026-10-30), CPU only.
Input: a TP rank harness run with OWNRT_PREFILL_DRAIN_TRACE=1 (probe build), RUN/rank<r>/prefill-drain-trace.jsonl: one line
per chunk; per drain (each exchange pair's card-0 drain, the loop's periodic event-ledger drain, the chunk's final drain) the host-clock ms from the drain's
start at which card 0 and card 1 were seen complete, the drain returned (events retired), and each card's exchange was
issued (-1 for the final drain). Both exchanges of a pair start only after its drain, so a card that finishes first idles
from its completion to its exchange's issue (plus the device's launch latency, not visible here).
Per full chunk: idle per card (completion -> issue), split into 'balance' (the other card still running: |done1 - done0|
charged to the earlier card) and 'turnaround' (later card's completion -> issue: detection, retirement, exchange issue),
grouped by the segment that ends at the drain (named by its exchange: gated / attention out-proj / qsa attention /
experts / final). Usage: analyze_drain_trace.py RUN RANK [--rows 256] [--json OUT]"""
import json, sys, collections, statistics as st
from pathlib import Path
run, rank = Path(sys.argv[1]), sys.argv[2]
rows = int(sys.argv[sys.argv.index('--rows') + 1]) if '--rows' in sys.argv else 256
out_path = sys.argv[sys.argv.index('--json') + 1] if '--json' in sys.argv else None
src = run / f'rank{rank}' / 'prefill-drain-trace.jsonl'
src = src if src.exists() else run / 'prefill-drain-trace.jsonl'  # kept evidence is flat
lines = [json.loads(x) for x in src.read_text().splitlines() if x.strip()]
full = [d for d in lines if d['rows'] == rows]
def kind(label):
    if label == 'final': return 'final (chunk end)'
    if label == 'periodic': return 'periodic (event ledger)'
    if label.endswith('tp_xcompact'): return 'experts (compact slots)'
    if label.endswith('qsa.attention.tp_xgather'): return 'qsa attention'
    if label.endswith('attention.tp_xgather'): return 'attention out-proj'
    if label.endswith('tp_xheads'): return 'gdn gated'
    return label
chunks = []
for d in full:
    by = collections.defaultdict(lambda: dict(drains=0, balance_ms=[0.0, 0.0], turnaround_ms=0.0, later_card1=0, later_card0=0, signed_card1_minus_card0_ms=0.0))
    tot = dict(idle_ms=[0.0, 0.0], balance_ms=[0.0, 0.0], turnaround_ms=[0.0, 0.0], drained_to_issue_ms=[0.0, 0.0])
    for label, d0, d1, drained, i0, i1 in d['sites']:
        k = by[kind(label)]; k['drains'] += 1
        late = max(d0, d1); k['signed_card1_minus_card0_ms'] += d1 - d0
        if d1 > d0: k['later_card1'] += 1
        elif d0 > d1: k['later_card0'] += 1
        early = 0 if d0 <= d1 else 1
        k['balance_ms'][early] += late - min(d0, d1); tot['balance_ms'][early] += late - min(d0, d1)
        if i0 >= 0 and i1 >= 0:
            for c, (done, iss) in enumerate(((d0, i0), (d1, i1))):
                tot['idle_ms'][c] += iss - done; tot['turnaround_ms'][c] += iss - late; tot['drained_to_issue_ms'][c] += iss - drained
            k['turnaround_ms'] += min(i0, i1) - late
    chunks.append(dict(position=d['position'], totals=tot, by_kind=by))
def mean(xs): return st.mean(xs) if xs else None
res = dict(run=str(run), rank=int(rank), rows=rows, full_chunks=len(chunks),
           mean=dict(idle_ms=[mean([c['totals']['idle_ms'][k] for c in chunks]) for k in (0, 1)],
                     balance_ms=[mean([c['totals']['balance_ms'][k] for c in chunks]) for k in (0, 1)],
                     turnaround_ms=[mean([c['totals']['turnaround_ms'][k] for c in chunks]) for k in (0, 1)],
                     drained_to_issue_ms=[mean([c['totals']['drained_to_issue_ms'][k] for c in chunks]) for k in (0, 1)]),
           by_kind={}, chunks=chunks)
kinds = sorted({k for c in chunks for k in c['by_kind']})
for k in kinds:
    rows_k = [c['by_kind'][k] for c in chunks if k in c['by_kind']]
    res['by_kind'][k] = dict(drains=rows_k[0]['drains'], balance_ms=[mean([r['balance_ms'][c] for r in rows_k]) for c in (0, 1)],
                             turnaround_ms=mean([r['turnaround_ms'] for r in rows_k]), later_card0=mean([r['later_card0'] for r in rows_k]),
                             later_card1=mean([r['later_card1'] for r in rows_k]), signed_card1_minus_card0_ms=mean([r['signed_card1_minus_card0_ms'] for r in rows_k]))
if out_path: Path(out_path).write_text(json.dumps(res, indent=1) + '\n')
m = res['mean']
print(f"rank {rank}: {len(chunks)} full chunks of {rows} rows; per chunk idle (completion -> own exchange issue) card0/card1 "
      f"{m['idle_ms'][0]:.2f}/{m['idle_ms'][1]:.2f} ms = balance {m['balance_ms'][0]:.2f}/{m['balance_ms'][1]:.2f} + turnaround "
      f"{m['turnaround_ms'][0]:.2f}/{m['turnaround_ms'][1]:.2f} (drain return -> issue {m['drained_to_issue_ms'][0]:.2f}/{m['drained_to_issue_ms'][1]:.2f})")
for k, v in res['by_kind'].items():
    print(f"  {k:26s} drains {v['drains']:3d}  balance idle card0/card1 {v['balance_ms'][0]:6.2f}/{v['balance_ms'][1]:6.2f} ms  "
          f"later card0/card1 {v['later_card0']:.0f}/{v['later_card1']:.0f}  sum(card1-card0) {v['signed_card1_minus_card0_ms']:+7.2f}  turnaround {v['turnaround_ms']:.2f}")
