# Retention

`rope.bf16` is the unchanged 4 MiB packet75 rotary table. It is required by
native startup and remains byte-pinned to its parent copy. Restore it from
packet75 and verify `parent-source-manifest.json`; no table is regenerated
with different arithmetic.

Generated checked mirrors, objects, binaries and raw CPU fixture outputs stay
under ignored `build/`. Rebuild with the commands in README. The build receipt
pins inherited objects and checked source closure, and the CPU report records
all four run hashes per view. Sealed small fixture receipts contain the raw
byte stream's hash, after the gate compares every raw byte; they are not model
outputs. No historical evidence is deleted or replaced.

`evidence/pre-bitonic/receipts.json.gz` is about 2.17 MB. Retention review:
keep it because it preserves the first, superseded candidate's complete build,
CPU, startup, plan and seal records before the bitonic revision. It contains
no model weights. Decode with `gzip.decompress`, then `json.loads`; keys are
original packet-relative paths and values are their exact UTF-8 JSON text.
Restore those values into a separate temporary directory, never over the final
candidate. Sixty archived source/gate hash bindings were checked against the
retained first seals. The first route source is retained beside the archive;
its old binaries are reproducible build products, not device-run evidence.
