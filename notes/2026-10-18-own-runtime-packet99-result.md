# Packet 99 result: IQ2 grid-lookup microbenchmark (2026-10-18 04:09 UTC, lane B, single card)

Device microbenchmark of the routed-expert gate/up kernel at full shapes, alternating orders, 40 pairs per candidate. Qualification needs ≤ 0.85 × production kernel time in both orders. Evidence: `experiments/own-xpu-runtime/stage2/packet99-iq2-grid/evidence/micro*/qualification.json`.

| Candidate | Time ratio vs production | Qualified |
|---|---|---|
| exp-slm (SLM-resident grid table) | 1.765 | no |
| exp-slm+halfcache | 1.777 | no |
| exp-compact-slm | 1.241 | no |
| exp-compact-slm+halfcache | 1.238 | no |
| exp-compact-global | 1.263 | no |
| exp-compact-global+halfcache | see qualification.json | no |

Production kernel event time is about 67–74 µs per call.

**Closed (DO-NOT-REPEAT):** relocating or compacting the IQ2 grid/sign tables (SLM, compact global) is slower; the production table is already effectively cached. Packet 86's `exp-constgrid` saving (about 0.57 ms per half) comes from removing the lookup dependency altogether (constant data lets the compiler fold the decode), not from table placement. Next exact gate/up ideas must cut the number of dependent lookups per weight, or overlap them with arithmetic, not move the table. E3 grid-word prefetch is also closed (packet 95).
