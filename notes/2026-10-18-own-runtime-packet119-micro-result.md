# Packet 119 expert DOWN-weight L2 warming: slower, closed (2026-10-18)

Lane B, card 2, `packet119-micro-B-1` 11:21–11:22 UTC, 384 real routes, both orders, exact. Second process pulled. No fault (count 2).

Runtime-reported global cache 25,165,824 B; down footprint 9,216,000 B per token (warm budget = full down set). Gate/up + down event time: production **97.60 µs**, warming **105.31 µs** → **1.079×** (orders 1.0799 / 1.0789; gate ≤ 0.85×). The extra warming loads compete with gate/up's own dependent reads instead of filling idle bandwidth, and the down kernel does not gain enough to repay them. Closed; together with packets 95, 99, 102, 104, 115 the expert GEMVs have resisted every exact scheduling/layout change except down-tile16.

Evidence: `experiments/own-xpu-runtime/stage2/packet119-down-warm/evidence/micro-B-1/qualification.json`.
