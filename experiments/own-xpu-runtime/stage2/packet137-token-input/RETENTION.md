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

Packet124b copies the binaries from packet124; both hashes also equal packet118.
`packet124-copy-identity.json` inventories the frozen copy. The orchestration
pins `inputs/packet124-native-identity.json` and checks every native source,
selection/configuration and runtime binary against it at readiness.
`inputs/k2-replay/` in the orchestration retains four exact gzip-compressed
packet124 K2 receipts (about 236 KB total), with original and compressed hashes.
The new gate restores these only to temporary scratch; it does not depend on
leaving the failed chain's ignored build tree at its original location.

Packet124c restores the original nine aliases, including the oracle directory.
Do not restore it by dereferencing the parent copy. The retained orchestration
`copy_bundle.py` and `inputs/symlink-audit.json` record exact targets and the
complete packet103/97 comparison. `prepare_chain.py` now preserves the seven
GNU fixture links instead of turning them back into hardlinks.

The frozen screen sealer requires source paths to stay inside the repository.
Run orchestration `seal_view.py` to recreate the ignored `build/sealed-inputs/`
byte snapshots from the real linked targets. Their original paths, local
snapshot paths and hashes are retained in `inputs/external-source-bindings.json`.
The chain adapter verifies both sides. The authority remains the real packet49
oracle, never these snapshots. Large source inputs listed above remain required
for exact identity and are restored from Git. Existing frozen trees and old
chain evidence remain intact.
