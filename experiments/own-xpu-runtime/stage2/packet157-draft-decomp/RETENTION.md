# Packet157 retention

The vendored source closure and report fixture are required to reproduce CPU
entry, report and native builds without mutable parent dependencies. Some
inherited JSON fixtures exceed 1 MiB; they are retained as regression inputs,
not packet157 measurements. Restore them from this packet's Git commit.

Build objects are ignored local artifacts. Immutable originals are hash-bound
in immutable-binaries.json and the original packet136 build recipe is retained
under lineage-inputs/packet136-history. Rebuild from the vendored sources and
record new hashes if local binary artifacts are unavailable; never silently
substitute an unverified object. Packet157's device evidence is still pending.
