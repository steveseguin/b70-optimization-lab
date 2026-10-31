#!/usr/bin/env python3
"""Launch JSONs for a lab build (research/tp/prefill-tp-overhead-2026-10-30): copies of this folder's e6daa268a3a8 launches
(contexts 65536 and 131072, both ranks) with only the engine binary replaced. Usage: make_bin_launches.py BINARY TAG"""
import json, sys
from pathlib import Path
D = Path(__file__).resolve().parent
binary, tag = sys.argv[1], sys.argv[2]
for r in (0, 1):
    for ctx in (65536, 131072):
        src = f'rank{r}-launch-c{ctx}-e6daa268a3a8.json'; out = D / f'rank{r}-launch-c{ctx}-{tag}.json'
        d = json.loads((D / src).read_text()); a = d['argv']
        i = next(k for k, x in enumerate(a) if x.endswith('/sc117-engine')); a[i] = binary
        d['changes'] = d.get('changes', []) + [f'prefill-tp-overhead lab build: binary {tag} ({binary}), otherwise {src}']
        if out.exists(): sys.exit(f'{out} exists')
        out.write_text(json.dumps(d, indent=1) + '\n'); print(out)
