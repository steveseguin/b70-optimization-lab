#!/usr/bin/env python3
"""CPU-only check of the OWNRT_DRAFT_CHUNK_BATCH schedule (research/tp/prefill-draft-batch-2026-10-30), before any
build or device run. Against a retained KV-only run (draft-chunk-sites.json, draft-kernel-choices.json of a rank-0
harness run with OWNRT_DRAFT_CHUNK_KV_ONLY=1) it checks that:
1. the KV-only derivation keeps exactly the 17 sites the batched schedule implements (mtp.hpp batch_kept()), in the
   row path's order;
2. every kept site has the kernel choice its batched kernel reproduces (draft_batch.hpp; mtp.hpp check_chunk_batch());
3. the batched launches, in order, read only values written earlier in the chunk, the chunk's two staged inputs,
   persistent state, or the two zero inputs of qsa.prepare whose outputs are dead (q, gate, iqn);
4. they write the same persistent state as the KV-only rows (keys, values, raw, pooled, position), and every value
   that is live at a row's start in the derivation is a chunk input or persistent;
5. the row buffers (n rows, token-major) have the sizes the kernels index, from the model geometry.
Usage: check_schedule.py RUN_DIR (a rank-0 run directory: RUN_DIR/rank0/draft-chunk-sites.json)."""
import json, sys
from pathlib import Path
run = Path(sys.argv[1]) / 'rank0'
sites = json.loads((run / 'draft-chunk-sites.json').read_text())
choices = json.loads((run / 'draft-kernel-choices.json').read_text())
g = dict(h=2560, low=320, qh=24, kvh=2, ad=256, ih=4, id=128)  # stage2/packet3/kernels/api.hpp Geometry
KEPT = ["merge.embedding_norm", "merge.hidden_norm", "merge.embedding_projected", "merge.projected", "merge.add", "begin.0",
        "blk.0.hc.a.norm", "blk.0.hc.a.low", "blk.0.hc.a.act", "blk.0.hc.a.gate", "blk.0.hc.a.mix", "blk.0.qsa.k", "blk.0.qsa.v",
        "blk.0.qsa.ik", "blk.0.qsa.prepare", "blk.0.qsa.pool", "commit.final"]
fail = []
def check(cond, msg):
    if not cond: fail.append(msg)
# 1. kept set and order
check(sites['kept'] == KEPT, f"kept sites differ: {sites['kept']}")
# 2. kernel choices (draft-kernel-choices.json "sites": packet59 / production / fused-at-producer)
want = {"merge.embedding_norm": "packet59", "merge.hidden_norm": "packet59", "merge.embedding_projected": "packet59",
        "merge.projected": "packet59", "merge.add": "fused-at-producer", "begin.0": "production", "blk.0.hc.a.norm": "packet59",
        "blk.0.hc.a.low": "packet59", "blk.0.hc.a.act": "fused-at-producer", "blk.0.hc.a.gate": "production",
        "blk.0.hc.a.mix": "production", "blk.0.qsa.k": "packet59", "blk.0.qsa.v": "packet59", "blk.0.qsa.ik": "packet59",
        "blk.0.qsa.prepare": "production", "blk.0.qsa.pool": "production", "commit.final": "production"}
for k, v in want.items():
    check(choices['sites'].get(k) == v, f"kernel choice {k}: {choices['sites'].get(k)} (batched for {v})")
for key, v in {"fuse_hidden_merge": "packet59", "fuse_hc_a_low": "packet59", "fuse_hc_a_mix": "production", "hc_a_gate": "production"}.items():
    check(choices['choices'].get(key) == v, f"selection {key}: {choices['choices'].get(key)} (batched for {v})")
# 3./4. dataflow of the batched launches (mtp.hpp issue_chunk_batch), row buffers by plan name
INPUTS = {"embedding", "merge.hidden"}                     # the staged rows (one copy each)
PERSIST = {"blk.0.qsa.keys", "blk.0.qsa.values", "blk.0.qsa.raw", "blk.0.qsa.pooled", "position", "error", "active"}
ZERO = {"blk.0.qsa.qgate", "blk.0.qsa.iq"}                # qsa.prepare's inputs of dead outputs
DEAD = {"blk.0.qsa.q", "blk.0.qsa.gate", "blk.0.qsa.iqn", "merge.projected"}
launches = [
    ("copy", ["(staging)"], ["merge.hidden", "embedding"]),
    ("merge.embedding_norm", ["embedding"], ["merge.embedding_norm"]),
    ("merge.hidden_norm", ["merge.hidden"], ["merge.norm"]),
    ("merge.embedding_projected", ["merge.embedding_norm"], ["merge.embedding_projected"]),
    ("merge.projected+merge.add", ["merge.norm", "merge.embedding_projected"], ["merge.projected", "streams"]),
    ("begin.0", ["active", "position"], ["error"]),
    ("blk.0.hc.a.norm", ["streams"], ["blk.0.hc.a.norm"]),
    ("blk.0.hc.a.low+act", ["blk.0.hc.a.norm"], ["blk.0.hc.a.low", "blk.0.hc.a.act"]),
    ("blk.0.hc.a.gate", ["blk.0.hc.a.act"], ["blk.0.hc.a.gate"]),
    ("blk.0.hc.a.mix", ["blk.0.hc.a.norm", "blk.0.hc.a.gate", "error", "active"], ["blk.0.hc.a.mix"]),
    ("blk.0.qsa.k", ["blk.0.hc.a.mix"], ["blk.0.qsa.k"]),
    ("blk.0.qsa.v", ["blk.0.hc.a.mix"], ["blk.0.qsa.v"]),
    ("blk.0.qsa.ik", ["blk.0.hc.a.mix"], ["blk.0.qsa.ik"]),
    ("blk.0.qsa.prepare", ["blk.0.qsa.qgate", "blk.0.qsa.k", "blk.0.qsa.iq", "position", "active", "error"],
     ["blk.0.qsa.q", "blk.0.qsa.gate", "blk.0.qsa.kn", "blk.0.qsa.iqn"]),
    ("blk.0.qsa.pool", ["blk.0.qsa.kn", "blk.0.qsa.v", "blk.0.qsa.ik", "position", "blk.0.qsa.raw", "active", "error"],
     ["blk.0.qsa.keys", "blk.0.qsa.values", "blk.0.qsa.raw", "blk.0.qsa.pooled"]),
    ("commit.final", ["error", "active", "position"], ["position"]),
]
written = set()
for name, ins, outs in launches:
    for i in ins:
        if i == "(staging)": continue
        check(i in written or i in PERSIST or i in ZERO, f"{name} reads {i} before the chunk writes it")
    written |= set(outs)
check(written & {"blk.0.qsa.keys", "blk.0.qsa.values", "blk.0.qsa.raw", "blk.0.qsa.pooled", "position"} == set(sites['persistent']),
      f"persistent writes {sorted(written & PERSIST)} vs derivation {sites['persistent']}")
check(set(sites['live_at_row_start']) <= INPUTS | PERSIST, f"live at row start beyond inputs and persistent: {sites['live_at_row_start']}")
for z in ZERO:
    check(z in sites['skipped'] or z not in KEPT, f"zero input {z} is a kept site's output")
check(not (DEAD - {"merge.projected"}) & set(sites['live_at_row_start']), "a dead qsa.prepare output is live")
# 5. row-buffer sizes (elements per row) as the kernels index them
rows = {"embedding": g['h'], "merge.hidden": 4 * g['h'], "merge.embedding_norm": g['h'], "merge.norm": 4 * g['h'],
        "merge.embedding_projected": g['h'], "merge.projected": 4 * g['h'], "streams": 4 * g['h'], "blk.0.hc.a.norm": 4 * g['h'],
        "blk.0.hc.a.low": g['low'], "blk.0.hc.a.act": g['low'], "blk.0.hc.a.gate": 4 * g['h'], "blk.0.hc.a.mix": g['h'],
        "blk.0.qsa.k": g['kvh'] * g['ad'], "blk.0.qsa.v": g['kvh'] * g['ad'], "blk.0.qsa.ik": g['id'],
        "blk.0.qsa.qgate": 2 * g['qh'] * g['ad'], "blk.0.qsa.iq": g['ih'] * g['id'], "blk.0.qsa.q": g['qh'] * g['ad'],
        "blk.0.qsa.gate": g['qh'] * g['ad'], "blk.0.qsa.kn": g['kvh'] * g['ad'], "blk.0.qsa.iqn": g['ih'] * g['id']}
check(set(rows) == written - PERSIST - {"error"} | ZERO, f"row buffers {sorted(set(rows) ^ (written - PERSIST - {'error'} | ZERO))}")
# kernels' per-token strides: K of each projection = the input row; rows = the output row
proj = {"merge.embedding_projected": ("merge.embedding_norm", g['h'], g['h'], 1), "merge.projected": ("merge.norm", g['h'], g['h'], 4),
        "blk.0.hc.a.low": ("blk.0.hc.a.norm", g['low'], 4 * g['h'], 1), "blk.0.hc.a.gate": ("blk.0.hc.a.act", 4 * g['h'], g['low'], 1),
        "blk.0.qsa.k": ("blk.0.hc.a.mix", 512, g['h'], 1), "blk.0.qsa.v": ("blk.0.hc.a.mix", 512, g['h'], 1), "blk.0.qsa.ik": ("blk.0.hc.a.mix", 128, g['h'], 1)}
for out, (x, r, k, per) in proj.items():
    check(rows[x] == k * per, f"{out}: input row {x} has {rows[x]} elements, the kernel reads {per} x {k}")
    check(rows[out] == r * per, f"{out}: output row has {rows[out]} elements, the kernel writes {per} x {r}")
    check(r % 4 == 0 or out in ("blk.0.hc.a.low", "blk.0.hc.a.gate"), f"{out}: DenseTokens<K,4> needs rows % 4 == 0")
n = 256
total = sum(v * 2 * n for v in rows.values()) + 4 * n
out = dict(schema='prefill-draft-batch.schedule-check.v1', source=str(run), kept=sites['kept'], launches=[l[0] for l in launches],
           row_buffers=len(rows), row_buffer_bytes_256=total, failures=fail, passed=not fail)
print(json.dumps(out, indent=1))
sys.exit(1 if fail else 0)
