# Packet 120 placement 25/23: −3.9%, closed (2026-10-18)

Lane B v4 grid on the bundle 7 line (packet 118 selection), all exact. No fault (count 2).

| Arm | Window (UTC) | Median tok/s | Hit ms | Miss ms |
| --- | --- | ---: | ---: | ---: |
| 0 production (24/24) | 11:32–11:36 | 58.174 | 14.922 | 25.768 |
| 1 25/23 | 11:37–11:42 | **55.906** | 15.510 | 26.774 |
| 2 production | 11:52 | refused: shared teardown left undrained by the failed packet124 K2 window (cascade), not rerun |

Moving one target layer to rank 0 adds ~0.59 ms to hits and ~1.0 ms to misses: rank 0 has little usable slack on this line (the head split already moved work there). Closed; packet 123's partial-layer move and packet 127's head-split retune must account for this.

Evidence: `experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p120-B-grid-{0-production,1-25-23}/`.
