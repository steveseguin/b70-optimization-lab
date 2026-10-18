# Budget retention

Keep the 47-class formulas and inventory, all 150 hash-bound captured hidden
inputs, source/checked-source closure, compiler logs, build receipts and
proposals. Captures total 3,072,000 bytes across 150 files; they are actual model
host-reference inputs, not generated substitutes. Checked source mirrors
record the exact compiled translation units. The binary/object files are
ignored local build products; build_budget.py rebuilds with the pinned
packet118 objects read-only. The original wrapper receipt is retained beside
the corrected one; the executable did not change. No device result exists yet.

All packet122 builds together must stay<=250 MB and root free >=25 GB.

The first budget milestone omitted the parent ignore rule and tracked its
sealed generated build. Keep that original committed build as evidence;
no binary or generated file has been deleted or moved. Subsequent candidate
and v5 build products follow the parent's ignore convention. The per-file
hash inventory is evidence/build-retention.json. The required 4 MiB
rope.bf16 table is copied from packet118 with its source hash. Build mirrors
derive fusion-rope.hpp from that parent's pinned lineage header.
