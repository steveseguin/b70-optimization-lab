# Packet 95 result: E3 `exp-grid-prefetch` lane-B grid (2026-10-18 03:22 UTC)

| View | tok/s (class-balanced) | vs control mean (55.488) |
|---|---|---|
| production (packet 84 selection) | 55.480 | — |
| E3 `exp-grid-prefetch` | 55.235 | **−0.46%** |
| production | 55.495 | — |

All views passed, with acceptance 0.787 unchanged.

**Closed (DO-NOT-REPEAT):** issuing the next IQ2 grid-word load before consuming the current tile costs more (extra registers/occupancy) than it hides. Status of packet 90's preregistered expert ladder:
- E1 halfcache: +0.28%, closed standalone;
- E2 scale-cache: does not fit (needs 9.44 GB vs 0.63 GB free on rank 1);
- E3 grid-prefetch: −0.46%;
- E5 shared-input: deferred.

**Next:** the packet 86 views (`exp-loadkeep`, `exp-constgrid`, `exp-onecached`, `hc-loadkeep`, running now on lane B) decide the next expert mechanism. The expert-dequantization bound is still about 1.14 ms per half (`exp-nodeq`).
