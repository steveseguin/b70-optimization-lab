# Packet58g artifact retention

The 4,194,304-byte `rope.bf16` is required by the source-relative native loader.
Restore from frozen `packet58f-onecard/rope.bf16`, SHA-256
`92a8f39204b5b8b1969ee2e5d3caac2310ced502bfeb9f51380b537d451ef390`.
It is a runtime constant, not a generated cache.

The source and historical evidence are copied from frozen 58f; its tracked files
are pinned by `parent58f-source-manifest.json`. The full-shape census and captured
argument ledger are below 1 MiB each and are retained to audit every production
allocation/submit. Older copied receipts retain their historical identities.
New 58g evidence is explicitly named and resealed.

`build/` is ignored compilation scratch, kept below 1 GB. Full-size CPU gates
reserve virtual extents but materialize only small setup buffers, never weights.
Fixture directories are temporary and removed by their gates. Installed compiler
and preexisting local build inputs are still required; this is not a publicly
reproducible package. No other packet's files or scratch were removed.
