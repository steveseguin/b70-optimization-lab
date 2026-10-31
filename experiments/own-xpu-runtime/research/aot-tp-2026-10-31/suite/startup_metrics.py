#!/usr/bin/env python3
"""Startup timeline of one lab server (research/aot-tp-2026-10-31/suite), from its work directory and its unit's journal.
Read-only. Usage: startup_metrics.py WORKDIR OUTDIR UNIT  -> OUTDIR/startup.json

- launch_to_ready_s: the unit's start (systemd "Started" entry) to the service's {"ready": true} journal line
  (journal realtime stamps, microseconds).
- first_request: the first self-test request (selftest-1, 87 prompt tokens read token by token, 32 output tokens): wall_s and
  prompt_wall_ms. With the JIT build its first half compiles every decode kernel; selftest-2 is the same request warm.
- first_half: each rank's first decode half (timings.jsonl position 0, the first row): half_completion_ms, enqueue_loop_ms
  (the JIT build compiles inside the enqueue loop) and prepare_ms; the second row for comparison. This is the number the
  ranks' --wait-seconds deadline races (rank 0's card-1 worker counts its release deadline from the loop's start).
- startup_gate: the one-time 13-case batched-prefill gate, from the start of its first request (utc - wall_s) to the end of
  its last, plus the first batched case's wall (its prompt rows run the batched-prefill kernels for the first time).
- jit_caches: files and bytes in each rank's SYCL and NEO cache directories at the end (fresh, empty directories at launch;
  the NEO directory receives one compiled module per JIT-built device image).
"""
import json, subprocess, sys
from datetime import datetime
from pathlib import Path

W, OUT, UNIT = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
res = dict(workdir=str(W), unit=UNIT)
j = subprocess.run(['journalctl', '--user', '-u', UNIT, '-o', 'json', '--no-pager'], capture_output=True, text=True).stdout
start = ready = None
for line in j.splitlines():
    try:
        e = json.loads(line)
    except ValueError:
        continue
    msg = e.get('MESSAGE') or ''
    if not isinstance(msg, str):
        continue
    t = int(e['__REALTIME_TIMESTAMP']) / 1e6
    if start is None and e.get('SYSLOG_IDENTIFIER') == 'systemd' and msg.startswith('Started '):
        start = t
    if ready is None and '"ready": true' in msg:
        ready = t
res['unit_started_epoch'] = start; res['ready_epoch'] = ready
res['launch_to_ready_s'] = round(ready - start, 3) if start and ready else None
runs = sorted((W / 'control').glob('run-*'))
req = [json.loads(l) for l in (runs[0] / 'requests.jsonl').read_text().splitlines() if l.strip()] if runs else []
ts = lambda r: datetime.fromisoformat(r['utc']).timestamp()
by = {r['label']: r for r in req}
if 'selftest-1' in by:
    res['first_request'] = {k: by['selftest-1'][k] for k in ('wall_s', 'prompt_wall_ms', 'decode_wall_ms', 'prompt_tokens', 'output_tokens')}
    res['first_request']['started_after_launch_s'] = round(ts(by['selftest-1']) - by['selftest-1']['wall_s'] - start, 3) if start else None
if 'selftest-2' in by:
    res['second_request'] = {k: by['selftest-2'][k] for k in ('wall_s', 'prompt_wall_ms', 'decode_wall_ms')}
gate = [r for r in req if r['label'].startswith('prefill-gate-')]
if gate:
    g0 = ts(gate[0]) - gate[0]['wall_s']; g1 = ts(gate[-1])
    batched = [r for r in gate if r.get('prefill_rows')]
    res['startup_gate'] = dict(requests=len(gate), seconds=round(g1 - g0, 3), started_after_launch_s=round(g0 - start, 3) if start else None,
                               first_batched=dict(label=batched[0]['label'], wall_s=batched[0]['wall_s'], prompt_wall_ms=batched[0]['prompt_wall_ms']) if batched else None,
                               batched_walls_s=[round(r['wall_s'], 3) for r in batched])
ev = sorted((W / 'evidence').glob('run-*'))
res['first_half'] = {}
for rank in (0, 1):
    p = ev[0] / f'rank{rank}' / 'timings.jsonl' if ev else None
    if p and p.exists():
        rows = []
        with open(p) as f:
            for line in f:
                rows.append(json.loads(line))
                if len(rows) == 2:
                    break
        keep = ('position', 'half_completion_ms', 'enqueue_loop_ms', 'prepare_ms', 'wait_ms', 'launches_issued')
        res['first_half'][f'rank{rank}'] = dict(first={k: rows[0].get(k) for k in keep}, second={k: rows[1].get(k) for k in keep} if len(rows) > 1 else None)
res['jit_caches'] = {}
if runs:
    for rank in (0, 1):
        for kind in ('sycl', 'neo', 'xdg'):
            d = runs[0] / 'ranks' / 'cache' / str(rank) / kind
            files = [f for f in d.rglob('*') if f.is_file()] if d.exists() else []
            res['jit_caches'][f'rank{rank}/{kind}'] = dict(files=len(files), bytes=sum(f.stat().st_size for f in files), exists=d.exists())
(OUT / 'startup.json').write_text(json.dumps(res, indent=1) + '\n')
print(json.dumps(dict(launch_to_ready_s=res['launch_to_ready_s'], first_request_s=res.get('first_request', {}).get('wall_s'),
                      first_half_ms={k: v['first']['half_completion_ms'] for k, v in res['first_half'].items()},
                      gate_s=res.get('startup_gate', {}).get('seconds'), neo_files={k: v['files'] for k, v in res['jit_caches'].items() if k.endswith('neo')})))
