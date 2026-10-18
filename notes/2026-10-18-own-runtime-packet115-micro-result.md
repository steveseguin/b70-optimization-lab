# Packet 115 large-GRF expert kernels: closed (2026-10-18)

Lane B, card 2, `packet115-micro-B-1` 09:49–09:52 UTC, 384 real routes, both orders, byte-exact. Second process pulled (result unambiguous). No fault (count 2).

Median candidate/control time ratio (both orders agree within 0.01):

| Design (256-GRF device image, zero spills) | vs production (default GRF) | vs production rebuilt large-GRF |
| --- | ---: | ---: |
| p95 E3 next-block | 1.696 | 1.175 |
| p95 E5 shared gate/up input | 1.497 | 1.034 |
| p99 IQ4 byte-pair SLM lookup | **0.995** | 0.935 |
| p102 V4 batch2/shared | 1.383 | 0.959 |

Production itself is ~1.44× slower when rebuilt in large-GRF mode: halving resident threads per core costs more latency hiding than the removed spills save. The expert GEMVs are latency/occupancy-bound, so register-hungry designs lose even with zero spills. Gate was ≤ 0.85× vs production; nothing qualifies. Closed; do not reopen large-GRF for expert kernels.

Evidence: `experiments/own-xpu-runtime/stage2/packet115-large-grf/evidence/micro-B-1/qualification.json`.
