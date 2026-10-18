# Packet103 retention

Source copies, focused deltas, exact CPU transcripts, compressed startup rows,
full-size arena censuses, immutable input snapshots and negative test evidence
are retained to reproduce and review the composition. Large JSON receipts may
exceed 1 MiB because they bind all 512 selections and all 5632 window checks;
size is not a performance claim. Gzip archives preserve exact uncompressed
hashes. Rebuild with the ordered commands in README using the pinned parent
source/object identities. Generated build artifacts are ignored. Delete only
this packet's scratch after its raw bytes and hashes have been retained.
No parent evidence is removed or rewritten.

The 4 MiB rope.bf16 is the exact inherited fixed arithmetic input needed for
this copied runtime. Restore from the committed packet97 source named in
copy-lineage.json and verify the recorded SHA256; it is not a generated cache.
