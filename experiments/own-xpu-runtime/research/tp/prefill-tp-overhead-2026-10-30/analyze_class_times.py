#!/usr/bin/env python3
"""Per-class device time of one-card batched prefill (research/tp/prefill-tp-overhead-2026-10-30), CPU only.
Input: a rank harness run on ONE card with --timing class (launch=timing) and OWNRT_SITE_TRACE=1, so every prefill site
is its own class (its full label) in RUN/rank<r>/class-times.json (sum of the sites' GPU event durations over the run).
The run reads `chunks` full prefill chunks and a few decode halves; the decode share is subtracted with a second run of the
same steps and a token-by-token prompt, or bounded (--decode-ms) when not given.
Each class is labelled by what four-card TP does with it (rank.hpp transform under the tptsxqckh flags): split (each card
does half: heads, rows or expert slots) or replicated (both cards do all rows).
Usage: analyze_class_times.py RUN RANK CHUNKS [--json OUT]"""
import json, re, sys
from pathlib import Path
run, rank, chunks = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
out_path = sys.argv[sys.argv.index('--json') + 1] if '--json' in sys.argv else None
d = json.loads((run / f'rank{rank}' / 'class-times.json').read_text())
SPLIT = {'gdn.qkv', 'gdn.z', 'gdn.a', 'gdn.b', 'gdn.conv', 'gdn.recurrence', 'gdn.gated', 'attention', 'qsa.qgate', 'qsa.k', 'qsa.v',
         'qsa.prepare', 'qsa.pool', 'qsa.attention', 'expsgate', 'expsup', 'expsact', 'expsdown', 'expsgate.check', 'expsup.check', 'expsdown.check'}
def cls_of(label):
    m = re.match(r'blk\.\d+\.(.*)$', label)
    return m.group(1) if m else label
agg = {}
for c in d['classes']:
    if c['class'].startswith('draft.'):
        k, kind = 'draft:' + cls_of(c['class'][6:]), 'draft'
    else:
        k = cls_of(c['class']); kind = 'split' if k in SPLIT else 'replicated'
    a = agg.setdefault(k, dict(kind=kind, device_ms=0.0, launches=0)); a['device_ms'] += c['device_ms']; a['launches'] += c['launches']
total = sum(a['device_ms'] for a in agg.values() if a['kind'] != 'draft')
per_chunk = {k: dict(kind=a['kind'], ms_per_chunk=a['device_ms'] / chunks, share=a['device_ms'] / total if a['kind'] != 'draft' else None, launches=a['launches'])
             for k, a in sorted(agg.items(), key=lambda x: -x[1]['device_ms'])}
rep = sum(v['ms_per_chunk'] for v in per_chunk.values() if v['kind'] == 'replicated')
spl = sum(v['ms_per_chunk'] for v in per_chunk.values() if v['kind'] == 'split')
res = dict(run=str(run), rank=int(rank), chunks=chunks, target_ms_per_chunk=rep + spl, replicated_ms_per_chunk=rep, split_ms_per_chunk=spl,
           tp_per_card_compute_ms=rep + spl / 2, perfect_split_ms=(rep + spl) / 2, classes=per_chunk)
if out_path: Path(out_path).write_text(json.dumps(res, indent=1) + '\n')
print(f"rank {rank}: {rep + spl:.1f} ms per chunk on one card (replicated {rep:.1f}, split {spl:.1f}); TP per card if only replicated work "
      f"stays whole: {rep + spl / 2:.1f}; perfect split {(rep + spl) / 2:.1f}")
for k, v in per_chunk.items():
    if v['ms_per_chunk'] >= 0.5: print(f"  {k:24s} {v['kind']:10s} {v['ms_per_chunk']:8.2f} ms  launches {v['launches']}")
