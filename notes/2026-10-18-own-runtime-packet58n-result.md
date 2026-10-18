# Packet 58n one-card tile16-only screen: +23%, qualifies (2026-10-18)

Lane A, card 0, whole host (lane B paused 11:58–12:21), packet 58n `card0-loo-a`, one model load per arm, 12 prompts × 128 tokens, all 12/12 exact vs the packet 49 oracle. No fault (count 2).

| Arm | Window (UTC) | submission100 median | fixed64 median |
| --- | --- | ---: | ---: |
| production-before | 11:54–12:03 | 20.999 | 20.839 |
| **down-tile16 only** | 12:04–12:11 | **26.274** | 26.333 |
| production-after | 12:13–12:21 | 21.336 | 21.162 |

tile16-only beats the better production arm by **+23.1%**. Packet 125's transfer micro had shown the tile16 layout raises zero-copy miss bandwidth 1.27× (exact); on one card the expert misses stream over PCIe every token, so the layout matters far more than on two cards. The production arms here (21.0–21.3) are slower than packet 58k's production arm earlier today (24.97), so host conditions vary between windows; the bracket controls bound this comparison. The port view (tile16 + route-fast + rec-both-plus) lost 11% in packet 58k because of host-side page faults, not tile16.

Next: packet 58p (one-card record chain for the tile16-only view, readiness requires this bracket at ≥ +0.5%) runs in the whole-host gap after bundle 7's 2-card chain (`p58p-chain` waiter).

Evidence: `experiments/own-xpu-runtime/stage2/packet58n-onecard-loo/evidence/card0-loo-a/*/WSCREEN/summary.json`.
