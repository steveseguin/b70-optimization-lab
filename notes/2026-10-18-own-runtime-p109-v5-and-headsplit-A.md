# Packet 109 v5 bracket and packet 105b head split lane-A confirm (2026-10-18)

## Packet 109 other-fusion (72 fewer launches per half), v5 one-load bracket, lane B
`packet109-v5-B`, 08:29–08:38 UTC, one model load, A/B/A/B/A, all 13 exact, control drift 0.44% (limit 3%).
**Strict candidate/control ratio 1.00318 (+0.32%)**, both candidates faster than all controls.
Removing 72 launches per half saves only ~0.05 ms per half: launch gaps are mostly hidden behind queued work (consistent with review 16). The small kernels' own execution latency (route 18.8 µs, combine 11.4 µs …, packet 110 roofline) is the cost, not their launch.
Evidence: `experiments/own-xpu-runtime/stage2/packet109-other-fusion/evidence/p109-v5-B/bracket-summary.json`.

## Packet 105b head split, lane-A confirm (packet 106b confirm jobs)
| Arm | Window (UTC) | Median tok/s | Hit ms | Miss ms |
| --- | --- | ---: | ---: | ---: |
| 0 production | 08:27–08:31 | 55.041 (low outlier) | 16.036 | 26.724 |
| 1 head split | 08:32–08:36 | **56.402** | 15.462 | 26.571 |
| 2 production | 08:37–08:41 | 56.190 | 15.543 | 26.628 |
All exact. **+0.38% over the better control** (lane B grid: +0.36%). Consistent on both lanes, below the +0.5% single-lever bar.

## Decision
Neither lever clears +0.5% alone; together ≈ +0.7%. Bundle 6 (packet 111) will test **base (packet 103) + fusion + head split** as one composite candidate; the composite must clear +0.5% on both lanes with all prompts exact before a chain.
