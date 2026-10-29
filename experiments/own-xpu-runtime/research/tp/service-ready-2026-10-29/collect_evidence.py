#!/usr/bin/env python3
"""Copy the small evidence of finished driver runs (summary, state hashes, TP exchange/compare/plan JSONs, census
totals per card) from the RAM run directory into evidence/<run>/. Usage: collect_evidence.py RUNS_DIR NAME..."""
import collections, json, shutil, sys
from pathlib import Path
D = Path(__file__).resolve().parent
runs = Path(sys.argv[1])
for name in sys.argv[2:]:
    src, dst = runs / name, D / 'evidence' / name
    dst.mkdir(parents=True, exist_ok=False)
    rank = next(r for r in ('rank1', 'rank0') if (src / r).is_dir())
    for f in ('summary.json',):
        if (src / f).exists(): shutil.copy(src / f, dst / f)
    st = src / rank / 'state-2147483647' / 'state.json'
    if st.exists(): shutil.copy(st, dst / 'state.json')
    ds = src / rank / 'draft-final-state' / 'all-state.json'
    if ds.exists(): shutil.copy(ds, dst / 'draft-all-state.json')
    for f in ('tp-exchange.json', 'tp-replicate-compare.json', 'tp-plan.json', 'prefill-allocation.json', 'prefill-shadow-pack.json', 'receipt.json'):
        if (src / rank / f).exists(): shutil.copy(src / rank / f, dst / f)
    c = src / rank / 'census.json'
    if c.exists():
        census = json.loads(c.read_text()); cards = collections.Counter()
        for a in census['allocations']:
            if a['live'] and a['memory'] == 'device': cards[a['label'].split(':')[0]] += a['bytes']
        (dst / 'census-totals.json').write_text(json.dumps(dict(device_bytes_by_card=dict(cards), totals=census['totals']), indent=1) + '\n')
    log = src / f'{rank}.log'
    if log.exists(): (dst / f'{rank}-log-tail.txt').write_text('\n'.join(log.read_text().splitlines()[-40:]) + '\n')
    print(name, sorted(p.name for p in dst.iterdir()))
