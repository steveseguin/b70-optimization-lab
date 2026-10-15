# SPEED2 retained evidence

All files here were produced by CPU source analysis, metadata-only plan checks,
mini-model checks, compilation, or seal-binding tests. No device executable was
run. `attribution-input-hashes.json` binds read-only qualifying device receipts;
those receipts stay under the coordinator's protected result directories.

`before-build-receipt.json` is the exact SPEED1 seal. Before-source files and the
two verified JSONL/gzip archives preserve the prior qualification code and build,
CPU-test and admission receipts. Nothing was removed from a device result tree.

`plan-writer-sites.json.gz` retains every per-site scratch bound for all48 actual
plan/dispatch constructions. `write-set-proof.json.gz` retains every snapshot
extent, old allocation size and new capture range for both placements, both
production capacities, and positions100/128/214. Both are deterministic gzip JSON
and are hash-bound by the corresponding gate receipts. They are not tensor bytes.

The root `speed2-snapshot-gates.json` may exceed1 MiB because it preserves full
state hashes, bank/launch metadata and timings for every independent mini owner,
including deliberately failing omissions. Its exact CPU scratch archives are
listed by path and digest in that gate and `mini-cases.json`; the storage helper
verifies archive contents before deleting only those CPU scratch directories.
Do not drop these records based on size. Restore text evidence with the existing
`storage.py` streamed archive format, or rerun `speed2_snapshot_gate.py` using the
recorded host binary/source identity. No model weights are needed for that gate.
