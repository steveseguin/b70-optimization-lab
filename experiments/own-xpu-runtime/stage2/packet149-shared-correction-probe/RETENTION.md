# Packet149 retention

The packet retains its closed source and exact new native binaries, the inherited
immutable object links needed for linking, fixed oracle prompt inputs, compact
CPU receipts, and the payload census. `retention-census.json` lists every regular
file at least 1 MiB with its hash and purpose. No model weights are included.

The `native-base` checked source and `v5/native-src` overrides reproduce the
entry binary. Run `v5/p149_v5_build_engine.py` with the documented nice/affinity,
Python `-B` and stdin `/dev/null`; it serializes builds through the ops arbiter.
It verifies every inherited ELF input against `immutable-binaries.json` before
linking and records both commands and source/binary hashes. The native test
binaries rebuild through `v5/controller_gate.py` and `v5/transport_gate.py`.
Exact compiler identity and commands are in `v5/engine-commands.json` and
`v5/evidence/build.json`; historical packet136 commands remain under lineage.

The fixed prompt input blobs are required by the complete oracle manifest check.
They are vendored without alteration and do not hold model weights. Original
packet136 symlink objects are retained separately from the active source closure;
no new source pin follows them to a mutable sibling packet. Recreate those
objects from `lineage-inputs/vendor-origin.json` if needed, preserving the literal
link text. The active oracle link is always checked by its original binding.

Unused copied legacy full-shape fixture payloads were omitted from this new
packet; originals in packet145 and earlier trees remain untouched. CPU regression
runs against retained packet145 evidence read it in place and redirect report
writes to temporary scratch. Generated Python caches are excluded.
