# Packets 92 and 94: first-lane grid results (2026-10-18 04:47–04:51 UTC)

## Packet 92 rank-1 reply-first (lane A)
| View | tok/s | hit ms |
|---|---|---|
| production | 55.444 | 15.795 |
| reply-first | 55.466 | 15.711 |
| production | 55.468 | 15.696 |

**No gain** (−0.004% vs the stronger control). Deferring rank-1 reporting after the next draft submit does not move the critical path measurably, so packet 76's housekeeping is no longer on it after `ordered`. Closed (DO-NOT-REPEAT).

## Packet 94 HC norm fused into its consumer (lane B)
| View | tok/s | hit ms |
|---|---|---|
| production | 55.029 | 15.793 |
| hc-normfuse | **42.676** | 19.987 |
| hc-normfuse+weightcache | 42.028 | 20.400 |
| production | 55.458 | 15.649 |

**−23%.** Recomputing the 2,560-element HC norm trees inside every consumer workgroup costs far more than the latency-bound norm launches it removes (about 0.19 ms per norm per half). Closed (DO-NOT-REPEAT): any norm fusion must not duplicate the reduction per workgroup.
