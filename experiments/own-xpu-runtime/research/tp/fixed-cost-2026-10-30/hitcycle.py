#!/usr/bin/env python3
"""Hit-cycle composition of the end-gate servers (CPU only): the retained controller trace of each server's 3,490-token
request (64 decode positions), through research/tp/miss-stall-2026-10-29/analyze.py one(). Usage: hitcycle.py WORKDIR...
(the lab servers' work directories, /dev/shm/tp-svc-fc-20261030/arm-<name>-c65536 or their RAID copies).
Writes results/hitcycle-endgate.json."""
import json, statistics as st, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'miss-stall-2026-10-29'))
import analyze as M  # noqa: E402
out = {}
for w in sys.argv[1:]:
    d, rows, stamps, r0 = M.one(Path(w))
    hits = [r for r in rows if r['hit']]; misses = [r for r in rows if not r['hit']]
    m = lambda k, rs=hits: round(st.median([r[k] for r in rs if r.get(k) is not None]), 4)
    out[Path(w).name] = dict(intervals=len(rows), hits=len(hits), misses=len(misses), hit_interval=m('interval'),
                             miss_interval=m('interval', misses) if misses else None, rank1_wall=m('rank1_wall'),
                             rank0_spec_wall=m('rank0_spec_wall'), draft_wall=m('draft_wall'), snapshot=m('snapshot'),
                             rank0_path=m('rank0_path'), rank1_path=m('rank1_path'), ctrl=m('ctrl'),
                             rank0_later_fraction=round(sum(r['rank0_late'] > 0 for r in hits) / len(hits), 3),
                             decode_wall_ms=round(d['decode_wall_ms'], 3))
    print(Path(w).name, json.dumps(out[Path(w).name]))
(HERE / 'results' / 'hitcycle-endgate.json').write_text(json.dumps(out, indent=1) + '\n')
