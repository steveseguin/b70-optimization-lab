# Retention

Retain all source/config deltas, pinned source snapshots, CPU gates, failed preparation receipts, launch logs and device summaries. Large native build outputs and per-window raw run trees remain ignored with paths and hashes in receipts. Parent packets are immutable.

The first CPU derivation refused a generated receipt replacing its inherited name. It ran no device work and remains at `/tmp/p196-preparation-20261023/attempt1-packet` and `attempt1-ops`; its log is copied into `lineage/preparation-attempt1.log`. The fix excludes chain-flags and pin-relocation from inherited receipts before regenerating them for this chain.
