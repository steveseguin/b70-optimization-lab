# Retained packet168 inputs

Keep the private source, failed preparation receipts, complete repository
negative-method search and real parent token/timing streams. None is a new
device result. The gzip streams are deterministic compressed snapshots of
historical JSON receipts; source paths and hashes are in
`evidence/real-parent-replay.json`.

The single4MiB rotary table under `native-source/repo/.../packet131-snapshot-banks/rope.bf16`
is an unchanged required runtime constant, SHA256
`92a8f39204b5b8b1969ee2e5d3caac2310ced502bfeb9f51380b537d451ef390`.
Restore it from the identical relative path under
`../packet165-warm-prefill/two-card/native-source/` and verify that hash.
It is intentionally tracked despite exceeding1MiB; it closes the native source's
absolute constant dependency without borrowing a mutable runtime file.

Build objects, executables and synthetic CPU scratch are ignored. Restore each
`build/objects/` member from the same relative path in the frozen
`../packet165-warm-prefill/two-card/` tree, verifying
`lineage/kernel-objects.json`. The exact compile/link commands are in
`lineage/build-inputs.json`; `build_engine.py` serializes them through the frozen
shared compiler turn. This is a local research packet, not a public recipe.

`patch_native.py` reconstructs its three private changed headers from the
frozen packet165 source and retains the deltas in `lineage/*.patch`.
`prepare_cpu.py` uses the pinned frozen packet163 preparation builder and
packet151 marker backend; its generated transport actually implements snapshot
byte copies. Those generation dependencies and modifications are retained in
the builder source and origin receipt. Never restore the initial marker-only
fixture as the qualified real-copy fixture.
