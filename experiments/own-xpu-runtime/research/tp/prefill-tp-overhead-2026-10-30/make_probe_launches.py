#!/usr/bin/env python3
"""Launch JSONs for the probe build (research/tp/prefill-tp-overhead-2026-10-30): copies of this folder's e6daa268a3a8 /
timing launches with only the engine binary replaced. rank<r>-launch-c65536-timingp.json (one card, --timing class, for
the probe arms) and rank<r>-launch-c131072-<TAG>.json (TP arms). Usage: make_probe_launches.py BINARY TAG"""
import json, sys
from pathlib import Path
D = Path(__file__).resolve().parent
binary, tag = sys.argv[1], sys.argv[2]
for r in (0, 1):
    for src, dst in ((f'rank{r}-launch-c65536-timing.json', f'rank{r}-launch-c65536-timingp.json'),
                     (f'rank{r}-launch-c131072-e6daa268a3a8.json', f'rank{r}-launch-c131072-{tag}.json')):
        d = json.loads((D / src).read_text()); a = d['argv']
        i = next(k for k, x in enumerate(a) if x.endswith('/sc117-engine')); a[i] = binary
        d['changes'] = d.get('changes', []) + [f'prefill-tp-overhead probe build: binary {tag} ({binary}), otherwise {src}']
        out = D / dst
        if out.exists(): sys.exit(f'{out} exists')
        out.write_text(json.dumps(d, indent=1) + '\n'); print(out)
