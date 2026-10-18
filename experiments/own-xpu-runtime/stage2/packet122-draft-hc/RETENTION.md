# Packet122 retention and restoration

Retain source copies, focused delta, checked source mirror, input/provenance
maps, compiler logs, compressed exact-byte archives, shape archives, receipts,
seals and temporary queue plans. Inputs are shared read-only with the budget
packet; its150 captured hidden-state files total about 3 MB and each is 20 KB.
They are needed for identical device replay and are hash bound.

Object files and native executables are ignored local build products, not a
public release. Rebuild via the README's serial CPU commands on this host
with the pinned packet118 source/object closure and oneAPI 2026.0. All parent
objects are read-only. The budget and HC/v5 combined local builds are below
250MB; check free root space>=25GB before rebuilding. Do not remove frozen
parent objects or retained evidence to fit the cap.

The checked source mirror is retained compilation evidence, not a model cache.
Generated full-size numeric allocation fixtures are compressed only after
member-by-member byte verification by retain_shape.py. No source weight,
unique device result or prior experiment was deleted.

The first budget milestone omitted the parent ignore rule and tracked its
sealed generated build. Keep that original committed build as evidence;
no binary or generated file has been deleted or moved. Subsequent candidate
and v5 build products follow the parent's ignore convention. The per-file
hash inventory is evidence/build-retention.json. The required 4 MiB
rope.bf16 table is copied from packet118 with its source hash. Build mirrors
derive fusion-rope.hpp from that parent's pinned lineage header.
