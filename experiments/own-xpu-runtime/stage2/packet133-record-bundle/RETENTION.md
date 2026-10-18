# Packet133 retention and restoration

Retain the copied source, immutable lineage snapshots, two selection seals,
compressed GNU/Intel bytes, full-size censuses, startup archive, all argument
and queue tests, and negative-test evidence. Historical parent snapshots retain
their exact bytes and original paths; they are provenance, not a packet133 pass.
The active readiness and CPU results are in packet133-orchestration.

The ignored native build reuses packet130 v5 binaries by exact hash. Restore
those frozen artifacts using packet130's build instructions, then run this
packet's `reuse_build.py`. Restore parent fixture links using
`inputs/symlink-audit.json` in orchestration and `prepare_chain.py`; never copy
with symlink dereferencing. Regenerate local numerical CPU startup fixtures
with `full_shape.py` and `startup103.py`. Both use the copied new
`ops/compile_turn.py`. `seal_view.py` recreates external-source byte snapshots
while retaining the original authority links and verifying both identities.

Large inputs are necessary inherited evidence: `rope.bf16` (4,194,304 bytes),
`lineage-inputs/fusion-rope.hpp` (12,582,900 bytes), and
`lineage-inputs/packet103-composition-selection.json` (1,993,365 bytes).
Restore their exact bytes from Git. Retained compressed operator fixtures
restore with gzip; their receipts bind both compressed and raw hashes.
Build files, compiler caches and model payloads stay out of Git.

The copy excludes old device-chain/submission outputs and regular generated
build files. Every original symlink is copied independently and compared with
`find -type l`; the audit records 182 preserved links. No parent file is removed
or changed. Build budget is 300 MB; root floor is 25 GB.
