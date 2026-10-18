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
