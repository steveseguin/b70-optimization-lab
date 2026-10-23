# Retention

Retain all source/config deltas, pinned source snapshots, CPU gates, failed preparation receipts, launch logs and device summaries. Large native build outputs and per-window raw run trees remain ignored with paths and hashes in receipts. Parent packets are immutable.

The first CPU derivation refused a generated receipt replacing its inherited name. It ran no device work and remains at `/tmp/p196-preparation-20261023/attempt1-packet` and `attempt1-ops`; its log is copied into `lineage/preparation-attempt1.log`. The fix excludes chain-flags and pin-relocation from inherited receipts before regenerating them for this chain.

CI hygiene correction: 136 frozen `.o` payloads were removed from Git's index only; all remain unchanged on disk and in the seal. Their original parent locations and exact hashes are retained in [local-object-dependencies.json](local-object-dependencies.json), alongside unchanged `restore-inputs.json` and engine source binding. A fresh checkout requires these host-local frozen inputs before seal verification or build restoration. Restore only by copying an existing listed source after its digest matches, then verify the destination; no compilation is authorized by this preparation. The parent cache23 chain supplies harness objects and the qualified diet engine supplies its frozen snapshot objects. Missing or changed sources are a restoration blocker.

The original GitHub hygiene failure (run 39969733384), rejected closeout text and withdrawn READY/final-checks receipts are preserved under `lineage/`. No payload was erased and no shared hygiene exception was added.
