# Retention

The 4,194,304-byte `rope.bf16` is the exact immutable packet97 table, copied to
make the fixture independent of parent orchestration outputs. Its SHA256 is in
`source-origin.json`. Restore it from that source only after checking the hash.
It is an arithmetic constant, not a model weight or generated cache.

`build/` is ignored and capped at 200,000,000 logical bytes, including mirrors,
objects, executables and temporary proof links. No parent object is copied into
it. The scripts recreate binaries using the source/object provenance receipts.
The parent build must remain available; this is a lab experiment, not a public
standalone reproduction recipe. Logs, small comparison transcripts and failed
source are retained. No frozen packet, shared screen tree or old evidence is
removed to save space.
