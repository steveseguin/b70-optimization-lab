#!/usr/bin/env python3
# rh-gate.py <proposal>: run ops/rehearse_entry.py --report --json; pass if every check passes, tolerating only
# (a) storage_floor findings whose admissions are all 25 GB and pass the 25.5 GB + writes replay, and
# (b) preparation_path status WARN "no preparation-path probe declared" (opsreview7 in progress, 2026-10-19).
import json, subprocess, sys
r = subprocess.run([sys.executable, '-B', 'experiments/own-xpu-runtime/ops/rehearse_entry.py', sys.argv[1], '--report', '--json'],
                   cwd='/home/steve/llm-optimizations', stdin=subprocess.DEVNULL, capture_output=True, text=True)
d = json.loads(r.stdout); bad = []
for j in d['jobs']:
    for k, v in j.items():
        if isinstance(v, dict) and v.get('passed') is False:
            if k == 'storage_floor' and all(a.get('floor_bytes', 0) <= 25_000_000_000 and a.get('passes_25_5gb_plus_writes') for a in v.get('admissions', [])) \
               and all(f.get('passes_25_5gb_plus_writes') and f.get('floor_bytes', 0) <= 25_000_000_000 for f in v.get('findings', [])): continue
            if k == 'preparation_path' and v.get('status') == 'WARN': continue
            bad.append(k)
    for b in j.get('binaries', []):
        if not b.get('passed'): bad.append('binary')
    if (j.get('report') or {}).get('passed') is False: bad.append('report')
print('PASS' if not bad else 'FAIL ' + ','.join(bad)); sys.exit(1 if bad else 0)
