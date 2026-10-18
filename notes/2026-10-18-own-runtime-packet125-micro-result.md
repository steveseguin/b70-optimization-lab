# Packet 125 one-card miss transfer: best 1.27×, below the 1.5× gate, closed (2026-10-18)

Lane B, card 2, `packet125-micro-B-{1,2}` (11:53–11:56 UTC), no model load, 384 real per-layer miss cases (one-card receipts: ~33 misses, ~65 MB per token), all delivered bytes exact. Median per-layer miss wall time and useful bandwidth:

| View | B-1 µs | B-2 µs | Useful GB/s | vs production |
| --- | ---: | ---: | ---: | ---: |
| production (zero-copy) | 234.8 | 236.4 | 8.75 | 1.00 |
| **tile16 layout (zero-copy)** | 187.0 | 185.8 | 10.9 | **1.26 / 1.27** |
| BCS pipeline ×3 | 192.2 | 194.9 | 10.3 | 1.22 / 1.21 |
| BCS aligned / contiguous | ~221 | ~222 | 9.0 | 1.06 |
| BCS in-flight ×3 | 230 | 230 | 8.6 | 1.02 |
| BCS serial ×3 | 253 | 252 | 7.9 | 0.93 |

Kill gate ≥ 1.5× in both processes: nothing qualifies; closed. Copy-engine prefetch does not beat zero-copy materially; the tile16 layout's 1.27× miss-path gain is real and is being tested in-engine by packet 58n's tile16-only one-card screen (production / tile16 / production, whole host).

Evidence: `experiments/own-xpu-runtime/stage2/packet125-miss-transfer/evidence/micro-B-{1,2}/samples.jsonl`.
