#!/usr/bin/env python3
"""Per-step rank timings of the long-prompt request (3,490 prompt tokens, 64 decode tokens; the last request of each
arm, the only one the service retains) from the native controller's rank_trace (ranks/native-result.json): medians and
p10/p90 of rank 0's speculative halves, its redo halves, rank 1's halves and the draft, decode positions >= 3490.
Usage: trace_summary.py NAME=native-result.json ... > results/long-prompt-trace.json"""
import json, statistics as st, sys
out = {}
for arg in sys.argv[1:]:
    name, path = arg.split('=', 1); d = json.load(open(path))
    dec = [t for t in d['rank_trace'] if t['position'] >= 3490]
    def q(v): v = sorted(v); return dict(median=round(st.median(v), 3), p10=round(v[len(v) // 10], 3), p90=round(v[len(v) * 9 // 10], 3), n=len(v))
    spec = [t for t in dec if t['rank'] == 0 and t['op'] == 1 and t['speculative']]
    r1 = {t['position']: t for t in dec if t['rank'] == 1 and t['op'] == 1}
    late = [round((t['rank_completed'] - r1[t['position'] - 1]['rank_completed']) * 1000, 3) for t in spec if t['position'] - 1 in r1]
    out[name] = dict(source=path, decode_wall_ms=round(d['decode_wall_ms'], 1), decode_intervals=d['decode_intervals'],
                     rank0_speculative_half_ms=q([t['busy_ms'] for t in spec]),
                     rank0_redo_half_ms=q([t['busy_ms'] for t in dec if t['rank'] == 0 and t['op'] == 1 and not t['speculative']]),
                     rank1_half_ms=q([t['busy_ms'] for t in dec if t['rank'] == 1 and t['op'] == 1]),
                     draft_ms=q([t['busy_ms'] for t in dec if t['rank'] == 0 and t['op'] == 9]),
                     rank0_spec_half_end_minus_rank1_end_ms=q(late))
print(json.dumps(out, indent=1))
