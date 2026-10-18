# Packet101 retention and restoration

The copied sources, selection manifests, source diff, compressed fixture bytes,
case logs, full startup matrix and seals are evidence. Keep them, including the
failed preparation logs. The copies preserve packet97's exact implementation
while leaving every existing packet and shared wrapper untouched.

Two new tracked artifacts exceed 1 MiB:

- `rope.bf16` is the 4,194,304-byte exact packet97 input used by initialization.
  Its identical Git blob can be shared with packet97; do not silently replace
  it with newly calculated values. `copy-lineage.json` binds its source/hash.
- `evidence/full-shape.json` retains all 512 actual startup/admission results,
  commands, source hashes and links to compressed allocation/dispatch receipts.
  It is about 1.61 MB. Re-run `full_shape.py` against the same inputs to restore
  the evidence, rather than inventing or interpolating unchecked combinations.

`build/` and all nested build directories are ignored. Runtime binaries are
hardlinks to hash-checked packet97 builds, not new compiled engines. Retained
generated source mirrors support local verification. CPU fixture binaries,
objects and temporary queue/case directories have been removed after their
receipts were saved. The final cleanup measured 85,919,366 logical build bytes
before removing full-shape scratch and 64,755,902 afterwards, below 300 MB.
[Cleanup hashes](evidence/storage-cleanup.json).

To restore missing ignored build inputs, restore packet97's original artifacts,
then use this packet's `build_engine.py` and the CPU reproduction order in
[README](README.md). A clean clone alone lacks the inherited local runtime
builds and model input receipts. No public reproducibility claim is made.
