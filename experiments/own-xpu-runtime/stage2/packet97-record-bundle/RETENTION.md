# Packet97 retention

This is an originating-host research bundle, not a public clean-build recipe.
`copy-lineage.json` pins the packet91 copy. `build-device-receipt.json` and
`engine-commands.json` bind newly compiled units, their generated include closure
and all reused parent objects. Build artifacts and selection binary hardlinks
are ignored by Git. The full generated-source archive is retained after final
verification; it preserves exact source bytes referenced by the build receipt.

`rope.bf16` is the inherited 4 MiB runtime input and is retained at its expected
packet-local path. CPU reports over 1 MiB are necessary to bind all 128 compositions
and 256 post-load checks. Gzip operator transcripts/case logs and deduplicated
full-shape censuses preserve original bytes; synthetic per-invocation scratch is
removed immediately after verification. No source packet evidence is removed.

All view binaries hardlink the same new host/device pair. Fixture inputs are
hash-checked hardlinks to packet56/61's immutable CPU fixtures. New binaries can
be rebuilt from `engine-commands.json` and the frozen parent object closure;
`restore_links.py` verifies retained archive members and reconstructs selection
links after the packet's own compiled binaries are available. The 2.14 MB
`evidence/generated-cpu-evidence.tar.gz` preserves 199 generated/raw files;
every member was roundtrip checked against its original hash. Two archived
pre-final seal sets preserve their superseded bytes and manifests. They do not
admit a chain. Copied historical patch whitespace is kept byte for byte.
The pre-final archives are 56,423,213 and 56,465,772 bytes: each retains 896
original JSON members, including inherited source maps. Their consumers are
the closeout/audit history, not runtime admission. Restore into a temporary
directory with `tar -xzf`, then check each member against the corresponding
`pre-final-*-seals.json` manifest; never overwrite the final selections. The
large size does not authorize discarding those original evidence bytes.
Do not run inherited historical build/matrix helpers as packet97 gates.

The new build must stay below 1.5 GB and root free above 12 GB. Runtime chain storage
retains the larger inherited reserve. CPU preparation does not override it;
`storage_precheck.py` reports its current pass/failure independently.
