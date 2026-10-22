# Packet187 retention

**Engines.** `build/` is git-ignored. Restore the two engines with `place_v3.py`. It copies packet186
`v5/build/{device,gnu-host}/own-rt-iq3` and refuses unless the bytes equal packet186's build receipt
(device `693cc194...`). It recreates the 99 fixture symlinks, each checked against packet136's chain seal.
Then run `select_v3.py`, `guard_layout187.py` and the ops `seal187.py`.

**Sizes.** New disk bytes are about 157 MB allocated in total: about 110 MB in this packet (55.8 MB of it
in `build/`) and 13.6 MB in the ops dir. About 549 MB more appears under the packet only as hard links
to bytes that already exist elsewhere. That covers the fixture archive, the link targets and the
`device/`/`gnu-host/` mirrors.

**Ignored paths.** `/device/`, `/gnu-host/`, `/lineage-inputs/link-targets/` and
`/lineage-inputs/fixture-archive.tar.gz` are git-ignored. `guard_layout187.py` recreates them as hard
links. Packet185/186 `run/` trees and per-view summaries were **not** copied. `bracket_gate.py` reads
them where packet186 retained them and pins all 169 files by sha256.

**Keep:**

- `lineage-inputs/`;
- `lineage/packet187-guard-layout.json`;
- the ops `evidence/` receipts;
- `evidence/packet136-chain-evidence.json.gz`, which the submission rehearsal needs.

---

# Inherited retention notes (packet124-136, historical)

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

## Packet136 restoration authority

The text above describes inherited packet124c artifacts. For this packet,
`reuse_build.py` restores the two native runtime binaries from packet131b,
verifies its full CPU source closure and both native selections, and binds its
exact bank-state evidence. It does not use packet118's native binary identity.
The baseline operator fixtures still come from packet124c/packet118 and rerun
locally. Do not copy an entire historical build tree: preserve the 182 original
links via `copy_bundle.links()`/the symlink audit, restore only the named native
and CPU fixtures, then regenerate local mock builds under the shared compiler
turn. Preserve the recorded failed first compiler command as harness evidence.

The committed sources and compressed CPU receipts restore the reviewed packet;
the initial-copy helper is not an automatic generator of later source edits.
Keep packet131b and packet131's referenced proof artifacts and native binaries.
The unchanged large source constants listed above remain necessary. Build
outputs stay ignored; total new build storage must remain below 300 MB. No old
record-chain output is copied into the fresh packet136 chain folder.
