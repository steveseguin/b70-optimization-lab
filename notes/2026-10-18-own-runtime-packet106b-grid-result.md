# Packet 106b lane-B grid: head split +0.36%, draft split loses (2026-10-18)

Lane B (cards 2+3), v4 lanes wrapper, 12 prompts × 128 tokens, all exact vs `iq3-p49-split32-v1`; no fault (count 2). Packet 105b's reset fix had passed its device micro (07:28) and the 12-prompt × 64 smoke (07:31–07:34, one target suffix winner); packet 106b's combined smoke passed 07:57–08:01.

| Arm | Window (UTC) | Median tok/s | Hit ms | Miss ms |
| --- | --- | ---: | ---: | ---: |
| 0 production | 08:04–08:09 | 56.199 | 15.519 | 26.710 |
| 1 head split (105b) | 08:10–08:15 | **56.421** | 15.451 | 26.622 |
| 2 head + draft split | 08:16–08:20 | 55.870 | 15.677 | 26.545 |
| 3 production | 08:22–08:26 | 56.222 | 15.496 | 26.720 |

- Head split: **+0.36%** over the better control (packet model predicted +1.07%). It is the grid's exact winner by the packet rule but below the coordinator's +0.5% bar for a cross-lane confirm; the lane-A confirm was queued anyway at 08:27 because lane A was otherwise idle (evidence only).
- Draft prefix split: **loses** (hit +0.16–0.18 ms vs controls). Excluded from bundle 6.
- These grids use the packet 97-era production line (not packet 103's tile16); absolute rates are not comparable to the 57.2 tile16 line.

Evidence: `experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p106b-13e3630d590c-B-grid-*`.
