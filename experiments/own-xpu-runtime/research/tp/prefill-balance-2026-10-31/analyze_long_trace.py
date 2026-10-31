#!/usr/bin/env python3
"""Per-chunk prompt-reading timeline of one long request from the lab service's native-result.json rank trace (CPU only;
research/tp/prefill-speed-2026-10-29). Op 15 = batched prefill chunk (both ranks), op 9 = one per-row draft replay command,
op 29 = one draft chunk replay command (OWNRT_DRAFT_CHUNK_REPLAY). Busy = rank_received..rank_completed of a command.
Reports per rank: busy and idle seconds inside the prompt window, per-chunk busy distribution, the draft replay per chunk,
how rank 1's chunk k starts relative to rank 0's chunk k, and the critical-path split.
Usage: analyze_long_trace.py NATIVE_RESULT.json [--json OUT]"""
import json, sys, statistics as st
from pathlib import Path
p = Path(sys.argv[1]); out = sys.argv[sys.argv.index('--json') + 1] if '--json' in sys.argv else None
r = json.loads(p.read_text()); t = r['rank_trace']; w0 = r['work_start']
pf = {0: [x for x in t if x['op'] == 15 and x['rank'] == 0], 1: [x for x in t if x['op'] == 15 and x['rank'] == 1]}
end = max(x['rank_completed'] for x in pf[0] + pf[1])
dr = [x for x in t if x['rank'] == 0 and x['op'] in (9, 29) and x['rank_completed'] <= end + 5]
def q(v):
    v = sorted(v); n = len(v); return dict(min=v[0], p10=v[int(n * .1)], median=v[n // 2], p90=v[int(n * .9)], max=v[-1])
def idle(rank):
    rows = sorted((x for x in t if x['rank'] == rank and x['op'] in (15, 9, 29) and w0 <= x['rank_received'] and x['rank_completed'] <= end + 5), key=lambda x: x['rank_received'])
    s, prev = 0.0, None
    for x in rows:
        if prev is not None: s += max(0.0, x['rank_received'] - prev)
        prev = x['rank_completed']
    return s
chunks = len(pf[0]); assert chunks == len(pf[1])
draft_by_chunk = {}
for x in dr:
    k = (x['position'] - 1) // 256 if x['op'] == 9 else x['position'] // 256
    draft_by_chunk[k] = draft_by_chunk.get(k, 0.0) + x['busy_ms']
lag = [(pf[1][k]['rank_received'] - pf[0][k]['rank_completed']) * 1e3 for k in range(chunks)]
res = dict(source=str(p), prompt_wall_ms=r['prompt_wall_ms'], chunks=chunks, prefill_end_s=end - w0,
           rank0=dict(prefill_busy_s=sum(x['busy_ms'] for x in pf[0]) / 1e3, draft_busy_s=sum(x['busy_ms'] for x in dr) / 1e3,
                      draft_commands=len(dr), draft_ops=sorted({x['op'] for x in dr}), idle_s=idle(0), chunk_busy_ms=q([x['busy_ms'] for x in pf[0]]),
                      draft_per_chunk_ms=q(list(draft_by_chunk.values()))),
           rank1=dict(prefill_busy_s=sum(x['busy_ms'] for x in pf[1]) / 1e3, idle_s=idle(1), chunk_busy_ms=q([x['busy_ms'] for x in pf[1]])),
           rank1_start_after_rank0_chunk_ms=q(lag),
           first_last_chunk_ms={'rank0': [round(x['busy_ms'], 1) for x in pf[0][:3]] + [round(x['busy_ms'], 1) for x in pf[0][-3:]],
                                'rank1': [round(x['busy_ms'], 1) for x in pf[1][:3]] + [round(x['busy_ms'], 1) for x in pf[1][-3:]]})
res['rank0']['critical_ms_per_chunk'] = (res['rank0']['prefill_busy_s'] + res['rank0']['draft_busy_s']) * 1e3 / chunks
res['rank1']['busy_ms_per_chunk'] = res['rank1']['prefill_busy_s'] * 1e3 / chunks
print(json.dumps(res, indent=1))
if out: Path(out).write_text(json.dumps(res, indent=1) + '\n')
