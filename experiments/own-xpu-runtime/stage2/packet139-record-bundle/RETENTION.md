# Packet139 retention and restoration

Retain this source copy, `copy139.json`, original symlink targets, native reuse
receipt, startup proof bindings, local screen/chain seals and orchestration
checks. Preserve predecessor packet trees, their numerical evidence and all
negative results. Never restore with a dereferencing copy.

The ignored native binaries are exact copies of
`../packet137-token-input/v5/build/{device,gnu-host}/own-rt-iq3`.
Copy each to this packet's corresponding `build/` path, preserving executable
mode, then run `reuse_build.py` under the CPU restrictions. The receipt checks
both hashes and the complete actual native source/proof closure. Local screen
view binaries are hardlinks to those copies. Missing legacy fixture/input
links must be recreated with the exact strings in `copy139.json`; the external
fixture byte hashes and resolved targets are additionally recorded in
`../../ops/packet139-orchestration/inputs/external-source-bindings.json`.

The 1,271,398,400-byte token table is not duplicated or committed. Its read-only
path and SHA-256 are in `token-input-selection.json` and packet137's complete
GNU/Intel table proof. Rebuilding it is a separate authorized preparation,
using packet137's retained source and receipt; do not substitute another table.

Large copied source inputs are deliberate retention, not caches:
`rope.bf16` (4,194,304 bytes) preserves exact rotary constants;
`lineage-inputs/fusion-rope.hpp` (12,582,900 bytes) preserves their compiled
form; `lineage-inputs/packet103-composition-selection.json` (1,993,365 bytes)
preserves inherited composition provenance. Restore their exact bytes from
this commit or packet137 and verify their source hashes. Their size does not
justify discarding them. Native binaries and generated build directories stay
out of Git; source, small receipts and compressed exact CPU transcripts remain.

The copied inactive preparation scripts and v5 tree are provenance only.
Use the orchestration README's packet139 entry points for this composition.
