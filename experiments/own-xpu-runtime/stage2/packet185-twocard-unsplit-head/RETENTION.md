# Packet185 retention

Tracked: sources (identity-rewritten copy of packet183's harness, `lineage/packet185-copy.json`), the packet185 deltas,
`analysis/` (the 2026-10-22 lever synthesis and its replay scripts), CPU gate receipts and logs under `v5/evidence/`
(including the eight hashed full-shape archives `shape-*.tar.gz`, ~1 MB), and `lineage-inputs/`:

* `packet183-own/`: packet183's README-level certification, proposals, waiter, window receipts and the 13 evidence files
  this packet cites (build receipt of the reused engine, real census, full-shape, admission, both device summaries).
* `decision-fixtures/` (6.0 MB): the REAL device streams the s185 rule is tested on, reduced to the fields the interval
  model reads (packet183's 60 bracket requests with rank-0 packet150 scopes; packet106b's 36 v4 fresh-load requests).
  Every reduced file records its source path and sha256; the sources are local untracked trees.

Ignored and local (`/v5/build/`, `/build/`): byte copies of packet183's two linked engines and three gnu-host objects,
the 78 `inherited/` links to the pinned packet103/136 objects, and the CPU full-shape/controller fixtures. Recreate with
`python3 -B v5/p185_v5_build_engine.py` (copies + verifies, no compiler) then `v5/qualify_cpu.py --start full-shape`.
The device output directories named in the proposal (`v5/evidence/device-view{0..4}-*-B-p185`) must stay fresh.
