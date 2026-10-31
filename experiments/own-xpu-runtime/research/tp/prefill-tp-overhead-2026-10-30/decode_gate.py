#!/usr/bin/env python3
"""Decode-half gate of a lab build's default path against the committed binary (research/tp/prefill-tp-overhead-2026-10-30),
CPU only. Each run is a rank harness run (summary.json: spec_ms or half_ms, one entry per decode half; the first two
halves are warm-up and skipped). Per run: median and count of the decode halves; per group (e.g. the committed binary's
runs vs the lab build's): the mean of the run medians; the gate is |lab / committed - 1| <= LIMIT (default 0.003).
Prefill per 256-row chunk (prefill-host-trace.jsonl full chunks, via analyze_host_trace.py's mean) is reported alongside.
Usage: decode_gate.py --base RUN [RUN ...] --lab RUN [RUN ...] [--limit 0.003] [--json OUT]"""
import argparse, json, statistics as st, subprocess, sys
from pathlib import Path
D = Path(__file__).resolve().parent
ap = argparse.ArgumentParser(); ap.add_argument('--base', nargs='+', required=True); ap.add_argument('--lab', nargs='+', required=True)
ap.add_argument('--limit', type=float, default=0.003); ap.add_argument('--json'); a = ap.parse_args()
def halves(run):
    s = json.loads((Path(run) / 'summary.json').read_text()); h = s.get('spec_ms') or s.get('half_ms') or []
    return h[2:]
def prefill(run):
    rk = next(Path(run).glob('rank?'), Path(run))  # a harness run, or its kept evidence (flat)
    rows = [json.loads(x) for x in (rk / 'prefill-host-trace.jsonl').read_text().splitlines() if x.strip()] if (rk / 'prefill-host-trace.jsonl').exists() else []
    full = [r['wall_ms'] for r in rows if r['rows'] == 256][1:]  # the first full chunk carries the cold launches
    return st.mean(full) if full else None
res = {}
for name, runs in (('base', a.base), ('lab', a.lab)):
    rr = []
    for r in runs:
        h = halves(r); rr.append(dict(run=r, halves=len(h), median_ms=st.median(h), mean_ms=st.mean(h), prefill_chunk_ms=prefill(r)))
    res[name] = dict(runs=rr, mean_of_medians=st.mean(x['median_ms'] for x in rr),
                     prefill_chunk_ms=st.mean(x['prefill_chunk_ms'] for x in rr if x['prefill_chunk_ms']) if any(x['prefill_chunk_ms'] for x in rr) else None)
ratio = res['lab']['mean_of_medians'] / res['base']['mean_of_medians']
res.update(ratio=ratio, limit=a.limit, passed=abs(ratio - 1) <= a.limit)
if a.json: Path(a.json).write_text(json.dumps(res, indent=1) + '\n')
for name in ('base', 'lab'):
    for x in res[name]['runs']:
        print(f"{name:4s} {Path(x['run']).name:14s} halves {x['halves']:3d} median {x['median_ms']:.4f} ms  prefill chunk {x['prefill_chunk_ms'] or 0:.2f}")
print(f"decode half: lab / base = {ratio:.5f} ({(ratio - 1) * 100:+.2f}%), limit {a.limit * 100:.1f}% -> {'PASS' if res['passed'] else 'FAIL'}")
sys.exit(0 if res['passed'] else 1)
