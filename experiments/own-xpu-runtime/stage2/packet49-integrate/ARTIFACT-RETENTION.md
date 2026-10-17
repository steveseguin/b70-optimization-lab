# Packet49 storage and retention

Builds, oracle outputs and device-window outputs live below
`/home/steve/own-xpu-runtime-results/packet49-integrate/`. Packet-local symlinks
make these available to the harness. This directory is on the root filesystem;
its use keeps result trees separate but creates no additional free space.
Admission preserves the inherited finite budgets and free-space floor.

Keep source, new build/seal receipts, CPU gate summaries, review notes and
reproduction scripts in Git. Keep compiled objects/binaries and full oracle
payloads in the external result directory, with hashes in their receipts.
Rebuilding changes binary identity and requires resealing before new device
windows. Never run a device binary merely to test that it was built.

The CPU oracle writes each prompt once, validates token progression, required
layer fixtures and teardown, then emits a bound receipt. It retains the first
prompt's full fresh-process repeat, KD target-stream captures, and the
informational old-versus-new token diff. Large progress/timing logs are gzip
archived only after an exact hash round trip. Completion is a separate receipt,
not a mutation of the engine seal. Status verifies it before model admission.

Historical SPEED6 sources are recoverable at `34c62b433`. Packet47 and packet48
are retained under their existing identities; no source/build/result from those
sealed packets is changed. No pre-existing result, record, coredump, incident,
cache or unrelated untracked path is a cleanup target.

The unchanged 4MiB `rope.bf16` is a relative symlink to packet45's retained
table, verified byte-for-byte during preparation. The new seal binds its
contents; there is no duplicate table in Git. Restore it from the retained
packet45 table, not a newly generated approximation.

The inherited packet45 cleanup scripts assume their historical path layout.
Do not invoke them blindly against this external build tree. Any deletion of
new regenerable build objects must record exact scope and restoration commands;
any evidence consolidation must verify original bytes and update consumers.
