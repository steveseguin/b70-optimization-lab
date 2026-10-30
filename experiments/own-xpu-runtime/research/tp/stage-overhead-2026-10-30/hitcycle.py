#!/usr/bin/env python3
"""Hit-cycle composition of the current four-card service (tptsxqc, binary 5921bb96f630) from the retained controller
traces of the fault-ladder suite servers (CPU only). Reuses research/tp/miss-stall-2026-10-29/analyze.py one(): the
3,490-token request's 64 decode positions, per position rank 1's half, rank 0's speculative half (+ its p150 snapshot,
token-prep, layer-body and export segments), the draft and the controller gap. Output: results/hitcycle-tptsxqc.json."""
import json, statistics as st, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'miss-stall-2026-10-29'))
import analyze as M  # noqa: E402
ARCH = Path('/mnt/raid-models/ownrt-experiment-archives/2026-10-29/fault-ladder-suite-20261029')
out = {}
for arm in ('arm-tptsxqc-r1', 'arm-tptsxqc-r2', 'arm-tptsxq-r1', 'arm-tptsxq-r2'):
    d, rows, stamps, r0 = M.one(ARCH / arm)
    hits = [r for r in rows if r['hit']]
    m = lambda k, rs=hits: round(st.median([r[k] for r in rs if r.get(k) is not None]), 4)
    out[arm] = dict(intervals=len(rows), hits=len(hits), misses=len(rows) - len(hits),
                    hit_interval=m('interval'), rank1_wall=m('rank1_wall'), rank1_busy=m('rank1_busy'),
                    rank0_spec_wall=m('rank0_spec_wall'), rank0_spec_busy=m('rank0_spec_busy'), snapshot=m('snapshot'),
                    token_prep=m('token_prep_spec'), layer_body=m('layer_body_spec'), export=m('export_spec'),
                    draft_wall=m('draft_wall'), draft_to_spec_gap=m('draft_to_spec_gap'), ctrl=m('ctrl'),
                    rank0_path=m('rank0_path'), rank1_path=m('rank1_path'),
                    rank0_later_fraction=round(sum(r['rank0_late'] > 0 for r in hits) / len(hits), 3), rank0_late=m('rank0_late'),
                    rank0_rows=r0)
    print(arm, json.dumps({k: v for k, v in out[arm].items() if k != 'rank0_rows'}))
(HERE / 'results' / 'hitcycle-tptsxqc.json').write_text(json.dumps(out, indent=1) + '\n')
