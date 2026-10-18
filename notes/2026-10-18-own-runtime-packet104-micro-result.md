# Packet 104 tile16-transpose microbenchmark on real routes (2026-10-18 06:18–06:21 UTC, lane B, single card)

| Arm | Time ratio vs production |
|---|---|
| target-gate-tile16 | 0.898 |
| target-gate-halfcache-tile16 | 0.893 |
| target-shared-q6-tile16 | 0.951 |
| hc-gate-tile16 | 1.007 |
| target-router-tile16 | 1.026 |
| draft-gate-tile16 | 1.262 |
| draft-down-tile16 | 1.347 |
| shared-gate-up-tile16 | 1.496 |
| shared-down-tile16 | 2.095 |

None met the preregistered ≤ 0.85 gate.
- **Closed (DO-NOT-REPEAT):** tile16 for draft experts, shared expert, HC gates and router. They are slower or neutral, so their access patterns do not match target down's.
- **Coordinator override (explicit):** target gate/up is the largest single kernel (about 1.50 ms per rank-1 half). A 10–11% cut there plausibly yields +0.3–0.5%: packet 100's 0.695 micro became +2.09% / +1.68% in the engine. Lane B was otherwise idle, so Codex p104b finishes `target-gate-tile16` and `target-gate-halfcache-tile16` for one lane-B grid. The 15% gate stays the default for every other lever.

## Packet 104b lane-B grid (2026-10-18 06:48–07:07 UTC), baseline = packet 97 + down-tile16, all 13/13 exact
| View | tok/s | hit ms |
|---|---|---|
| production (p97 + down-tile16) | 57.110 | 15.234 |
| target-gate-tile16 | 56.914 | 15.283 |
| target-gate-halfcache-tile16 | 57.133 | 15.218 |
| production | 57.125 | 15.233 |

**Closed (DO-NOT-REPEAT): no in-engine gain.** tile16 is −0.35%; tile16 + half-cache is +0.01% (noise). The gate/up kernel's 10–11% microbenchmark cut does not reach the critical path. The lane-A confirmation was pulled; the coordinator's waiter rule (beat the stronger control by any margin) has been tightened to require ≥ +0.5%. Side result: the **packet 97 + down-tile16** baseline measures **57.11–57.13 tok/s** on lane B, previewing bundle 5.

## Packet 104b lane-A confirmation (07:07–07:21 UTC), all exact
| View | tok/s |
|---|---|
| production (p97 + down-tile16) | 57.257 |
| target-gate-halfcache-tile16 | 57.215 |
| production | 57.240 |

No gain on the record lane either; packet 104b stays closed. **The p97 + down-tile16 baseline measures 57.24–57.26 tok/s on lane A** (vs the packet 97 record chain's 56.087), previewing bundle 5 before packet 101's draft attention is added.
