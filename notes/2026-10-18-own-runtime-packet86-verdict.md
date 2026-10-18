# Packet 86 verdict: expert and HC limiters on rank 1 (2026-10-18 03:53 UTC)

These are non-exact diagnostic views (fenced out of bundles, chains and submissions). Shared pinned v4 screens, packet 84's selection. The table sums `estimated_ms_per_half` over rank-1 sites from `stage2/screen/v4-lanes/evidence/packet86-{A,B}-a/*/diagnostic-summary.json`; lane B, except `exp-nodeq` from lane A.

| View | expsgate (gate/up) | expsdown | hc.a.gate | hc.f.gate |
|---|---|---|---|---|
| production (B) | 1.495 | 1.208 | 0.604 | 0.592 |
| exp-nodeq (A; A production 1.500 / 1.211) | 0.811 | 0.780 | — | — |
| exp-constgrid | **0.923** | 1.277 | — | — |
| exp-loadkeep | 1.573 | 1.271 | — | — |
| exp-onecached | 1.227 | **0.849** | — | — |
| hc-nodeq | — | — | **0.418** | **0.419** |
| hc-constscale | — | — | 0.624 | 0.616 |
| hc-loadkeep | — | — | 0.627 | 0.615 |

## Verdict (packet 90 `PREREGISTRATION.md` table)
- **Gate/up: IQ2 table/sign dependency-bound.** A constant grid lookup removes 0.57 ms of the 0.68 ms dequant cost (loadkeep − constgrid ≈ 0.65 ms; constgrid − nodeq ≈ 0.11 ms). Cache locality is secondary (onecached −0.27 ms). Next: exact grid-lookup mechanisms, **packet 99** (SLM/register-resident or merged grid×sign tables). Grid-*word* prefetch (E3) is closed.
- **Down: cache/load-bound.** onecached −0.36 ms vs nodeq −0.43 ms; constgrid has no effect. Next per the table: E5 (gate/up shared input; locality) → E4 (slot coalescing), plus down-specific load-locality mechanisms.
- **HC gates: signed conversion / remaining dequant-bound.** hc-nodeq −0.19 ms per gate; scale-related views have no effect. H1 (FP32 weight cache) is closed at −3.25%. Next: H4 (tiled/partial FP32) → H2 only with scale-dependency evidence.
- Packet 85 sensitivity: +0.293 tok/s per 0.1 ms on rank 1, so the gate/up grid term is worth up to about +1.7 tok/s.
