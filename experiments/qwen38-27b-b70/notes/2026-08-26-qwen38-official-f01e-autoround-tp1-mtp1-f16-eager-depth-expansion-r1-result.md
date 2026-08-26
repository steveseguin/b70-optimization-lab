# Qwen3.8 official AutoRound TP1 eager/F16 MTP1 depth expansion r1

This is mixed Grade D coverage, not a promoted complete curve. All six exact cache-zero depth gates, acceptance gates, model verification, cleanup, and the full quality battery passed. Exact target-token parity passed only at 4K, 16K, 24K, and 32K, so those four cells are published as lower-grade measured evidence. The 2K and 8K outputs diverged at tokens 90 and 99 respectively and remain explicitly quarantined; x0 remains missing.

The runner correctly failed the whole arm closed (`quarantined-target-verification-failed`, rc39, `publication_authorized=false`). Per-depth publication is a later explicit human coverage adjudication and does not rewrite that receipt or imply automatic authority. Published decode values use the conventional 99-interval field; the distinct historical 100-event fields remain in the compact result. No protected route or other MTP/graph/KV/TP/runtime selector is replaced.

| Depth | Conventional tok/s | Historical tok/s | TTFT | Acceptance | Classification |
|---:|---:|---:|---:|---:|---|
| 2K | 7.526897906816153 | 7.602927178602174 | 2330.2020539995283 ms | 53/74 | quarantined, token 90 |
| 4K | 8.309260103763794 | 8.393192024003833 | 2937.1183600014774 ms | 56/71 | measured Grade D |
| 8K | 8.277242218230947 | 8.360850725485806 | 5910.425936992397 ms | 61/67 | quarantined, token 99 |
| 16K | 7.804595048897438 | 7.883429342320644 | 12146.145694001461 ms | 58/69 | measured Grade D |
| 24K | 7.615463263790375 | 7.692387135141794 | 18746.035040996503 ms | 57/70 | measured Grade D |
| 32K | 7.72237631436256 | 7.800380115517736 | 25747.598091998952 ms | 57/70 | measured Grade D |
