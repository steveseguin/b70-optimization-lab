# Packet 127 head-split retune: more rows to rank 0 loses, closed (2026-10-18)

Lane B v4 grid on the bundle 7 line; both split-point device micros passed (exact split-argmax incl. ties/nonfinite). No fault (count 2).

| Arm | Window (UTC) | Median tok/s | Hit ms |
| --- | --- | ---: | ---: |
| 0 production (46,080 suffix rows on rank 0) | 12:28–12:33 | 58.119 | 14.920 |
| 1 81,920 suffix rows | 12:34–12:41 | **56.987** | 15.264 |
| 2 122,880 / 3 production | pulled (decisive) | | |

Moving 35,840 more head rows to rank 0 costs ~0.34 ms per hit (−1.95%). Together with packet 120 (25/23 placement −3.9%), rank 0 has no usable slack on this line: rank-1 → rank-0 work moves are closed until the in-engine attribution (packet 128) shows otherwise.

Evidence: `experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p127-B-grid-{0-production,1-81920}/`.
