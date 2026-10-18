# Packet124 retention

Keep copied native source, immutable lineage inputs, parent snapshots, seals,
compressed exact-byte fixtures, allocation censuses and the startup archive.
`parent-snapshot/` retains original packet118 receipt bytes for comparison;
its embedded paths are provenance, not mutable parent readiness dependencies.
Current seals bind local receipts and fixed ancestor source/artifacts only.

The ignored build reuses packet118 native and CPU test binaries byte-identically.
Restore missing build artifacts by copying the matching packet118 `build/` tree
with symlinks preserved, then run `reuse_build.py` under the CPU restrictions.
It checks native source and binary hashes against the copied receipt before
creating any new seal. Original compiler commands remain in the parent snapshot.
Regenerate local CPU mock fixtures with `full_shape.py` and `startup103.py`.
No model payloads or generated caches belong in Git.

Large source inputs remain necessary: `rope.bf16` (4,194,304 bytes) retains
frozen rotary constants; `lineage-inputs/fusion-rope.hpp` (12,582,900 bytes)
is their frozen compiled form; `lineage-inputs/packet103-composition-selection.json`
(1,993,365 bytes) retains inherited composition provenance. Restore exact bytes
from Git. Compressed operator fixtures restore with gzip or the retained CPU
commands. Preserve unique negative evidence and prior packet trees.
