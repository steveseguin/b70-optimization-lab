# Packet 102 result: IQ2 gate/up lookup batching + shared input microbenchmark (2026-10-18 05:16 UTC, lane B, single card)

Microbenchmark of the gate/up kernel at full shapes, alternating orders. Qualification needs ≤ 0.85 × production time in both orders.

| Candidate | Time ratio vs production (both orders) | Qualified |
|---|---|---|
| exp-lookup-batch2 (issue lookups for the next 2 groups before consuming) | 0.981 (0.983 / 0.980) | no |
| exp-lookup-batch4 | 1.002 | no |
| exp-gateup-shared (E5: gate and up share activation loads) | 1.033 | no |

**Closed (DO-NOT-REPEAT).** With packet 99 (table relocation/compaction, 1.24–1.78× slower) and packet 95 (grid-word prefetch, −0.46%), every exact mechanism tried so far for the IQ2 gate/up dependency has failed: relocate, prefetch, batch, share input. Packet 86's `exp-constgrid` bound (≈0.57 ms per half) remains, but the compiler's constant folding is not reproducible exactly with a runtime table.

Coordinator note: the closed-build archive pass at 05:17 included packet 102's build tree while Codex p102 was still running. It was restored from the verified archive at 05:21 (366 files, checksums verified).
