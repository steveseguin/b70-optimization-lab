# Packet 130 head-suffix interleave: −1.61%, closed (2026-10-18)

Lane B, smoke (12 × 64, exact) 14:29–14:33 UTC, v5 one-load bracket `packet130-bracket-B` 14:34–~14:53 UTC on the bundle 7 line, all 13 exact, control drift 0.05%.

| View | Rate |
| --- | ---: |
| control | 58.131 / 58.154 / 58.162 |
| candidate (rank 0 runs the head suffix at the first ready layer boundary after the hidden import) | 57.229 / 57.282 |

Strict ratio **0.98395 (−1.61%)**. Packet 128b measured rank 1 waiting 1.2–1.6 ms per hit for rank 0's suffix rows; pulling the suffix forward removes part of that wait but delays rank 0's speculative half by the same work, and rank 1's next half waits on that half. On a single-CCS card the work only moves; the net is negative (consistent with packets 120 and 127: rank 0 has no spare time). Closed; packet 133's bundle 8 (sealed with this dimension) stays blocked.

Evidence: `experiments/own-xpu-runtime/stage2/packet130-suffix-interleave/v5/evidence/device-v5-B/bracket-summary.json`.
