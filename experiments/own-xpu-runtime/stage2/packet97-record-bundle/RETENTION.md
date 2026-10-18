# Packet97 retention

This is an originating-host research bundle, not a public clean-build recipe.
`copy-lineage.json` pins the packet91 copy. `build-device-receipt.json` and
`engine-commands.json` bind newly compiled units, their generated include closure
and all reused parent objects. Build artifacts and selection binary hardlinks
are ignored by Git. The full generated-source archive is retained after final
verification; it preserves exact source bytes referenced by the build receipt.

`rope.bf16` is the inherited4MiB runtime input and is retained at its expected
packet-local path. CPU reports over1MiB are necessary to bind all128 compositions
and256 post-load checks. Gzip operator transcripts/case logs and deduplicated
full-shape censuses preserve original bytes; synthetic per-invocation scratch is
removed immediately after verification. No source packet evidence is removed.

All view binaries hardlink the same new host/device pair. Fixture inputs are
hash-checked hardlinks to packet56/61's immutable CPU fixtures. New binaries can
be rebuilt from `engine-commands.json` and the frozen parent object closure;
the copied historical `restore_links.py` is not the packet97 restoration path.
Do not run inherited historical build/matrix helpers as packet97 gates.

The new build must stay below1.5GB and root free above12GB. Runtime chain storage
retains the larger inherited reserve. CPU preparation does not override it;
`storage_precheck.py` reports its current pass/failure independently.
