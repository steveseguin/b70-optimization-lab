# Packet 58r one-card one-load bracket: route-fast + rec-both-plus on tile16, inconclusive, closed (2026-10-18)

Lane A, card 0, whole host, 15:06–15:21 UTC (after a 14:58 host-admission refusal with no device work), one model load, A/B/A/B/A, 60 requests × 128 tokens, all exact vs the packet 49 oracle. No fault (count 2).

Rates: tile16 26.015 / **route-rec 26.551** / tile16 26.323 / **route-rec 26.419** / tile16 26.040. Minimum gain vs the best control **+0.37%** (gate +0.5%); control drift 1.18% (under the 3% bracket limit, but larger than the effect). Closed as inconclusive; the tile16 controls reproduce the 26.23 record line.

Evidence: `experiments/own-xpu-runtime/stage2/packet58r-onecard-v5/evidence/card0-v5-a/route-rec/WSCREEN/summary.json`.
