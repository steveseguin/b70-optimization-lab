#!/usr/bin/env python3
"""Small per-arm summary from the arm's /dev/shm work directory: rank census per card, DRM devices each rank held,
host-memory phases, rank logs' last lines. Usage: collect_arm.py WORKDIR OUTDIR"""
import collections, json, sys
from pathlib import Path
W, OUT = Path(sys.argv[1]), Path(sys.argv[2])
out = {}
for run in sorted((W / 'evidence').glob('run-*')):
    for rank in (0, 1):
        d = run / f'rank{rank}'
        row = {}
        c = d / 'census.json'
        if c.exists():
            census = json.loads(c.read_text())
            cards = collections.Counter()
            for a in census['allocations']:
                if a['live'] and a['memory'] == 'device':
                    cards[a['label'].split(':')[0]] += a['bytes']
            row['census_device_bytes'] = dict(cards)
            row['census_totals'] = census['totals']
        m = d / 'drm-memory-after_load.txt'
        if m.exists():
            row['drm_pdevs_after_load'] = sorted({l.split('\t')[-1].strip() for l in m.read_text().splitlines() if l.startswith('drm-pdev')})
        h = d / 'host-memory.jsonl'
        if h.exists():
            row['host_memory'] = [json.loads(l) for l in h.read_text().splitlines() if l.strip()]
        for name in ('lookup-residency.json', 'tp-exchange.json', 'receipt.json', 'failure.json', 'failure-before-teardown.json'):
            if (d / name).exists():
                try:
                    row[name] = json.loads((d / name).read_text())
                except ValueError:
                    row[name] = (d / name).read_text()[:2000]
        out[f'{run.name}/rank{rank}'] = row
(OUT / 'ranks-summary.json').write_text(json.dumps(out, indent=1) + '\n')
print(json.dumps({k: dict(census=v.get('census_device_bytes'), pdevs=v.get('drm_pdevs_after_load')) for k, v in out.items()}))
