# Packet128b boundaries

- Packet128's every-token recorder failed overhead at 42.211 tok/s. Do not rank it.
- Never subtract automatic-copy clocks from compute clocks. Zero-duration copy events are unresolved.
- SnapshotFlat and multi-item SnapshotBatch are compute kernels, even though their work copies bytes.
- Never average unsampled cycles as zero cost. Complete sampled prediction cycles are 10–16.
- Require every sampled cycle's 48 layers, both ranks, and hits plus misses across the sample.
- Never rank before the ≥0.90 ratio to 58.0 gate; JSON rankings must also be empty on failure.
- Sample costs and optimistic 20% savings are diagnostic projections, not measured gains.
- Preserve all parent symlinks. Do not copy old device receipts into a fresh output.
- Only one attribution-B load is registered; no legacy chain, resident service or retry.
