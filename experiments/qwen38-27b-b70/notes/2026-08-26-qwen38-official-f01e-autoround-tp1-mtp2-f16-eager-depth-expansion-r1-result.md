# Qwen3.8 official AutoRound TP1 eager/F16 MTP2 depth expansion r1

This is mixed Grade D coverage, not a promoted complete curve. All six exact cache-zero depth gates, acceptance gates, model verification, cleanup, and the full quality battery passed. Exact target-token parity passed only at 4K, 24K, and 32K, so those three cells are published as lower-grade measured evidence. The 2K, 8K, and 16K outputs diverged at tokens 90, 99, and 32 respectively and remain explicitly quarantined; x0 remains missing.

The runner correctly failed the whole arm closed (`quarantined-target-verification-failed`, rc39, `publication_authorized=false`). Per-depth publication is a later explicit human coverage adjudication and does not rewrite that receipt or imply automatic authority. Published decode values use the conventional 99-interval field; the distinct historical 100-event fields remain in the compact result. No protected route or other MTP/graph/KV/TP/runtime selector is replaced.

| Depth | Conventional tok/s | Historical tok/s | TTFT | Acceptance | Classification |
|---:|---:|---:|---:|---:|---|
| 2K | 9.937153642160142 | 10.03752893147489 | 2359.9275250016944 ms | 72/110 | quarantined, token 90 |
| 4K | 11.394116870048126 | 11.509208959644573 | 2951.627002999885 ms | 80/94 | measured Grade D |
| 8K | 11.346172448828067 | 11.460780251341482 | 5937.114834989188 ms | 82/94 | quarantined, token 99 |
| 16K | 10.989699795194069 | 11.100706863832393 | 12203.534041007515 ms | 80/96 | quarantined, token 32 |
| 24K | 9.85557002002922 | 9.955121232352747 | 18854.488349999883 ms | 76/102 | measured Grade D |
| 32K | 9.789228307267285 | 9.888109401280087 | 25905.252890006523 ms | 74/106 | measured Grade D |
