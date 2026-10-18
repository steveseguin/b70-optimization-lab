# Packet 117 HC gate: micro below gate, closed (2026-10-18)

Lane B, card 2, `packet117-micro-B-1` 11:19–11:20 UTC, complete current-mode layer harness, exact. Second process pulled. No fault (count 2).

hc.a.gate + hc.f.gate at context 128: production **44.38 µs**, packet 117 (parallel sigmoid work, unchanged reduction order, exact exceptional-value fallback) **43.54 µs** → **0.98×** (gate ≤ 0.70×). The HC gate GEMVs' ~31% of bandwidth is not explained by the sigmoid epilogue. Closed.

Evidence: `experiments/own-xpu-runtime/stage2/packet117-hc-gate/evidence/micro-B-1/native/iterations.jsonl`.
