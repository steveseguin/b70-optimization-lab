# Packet 114 draft-head prefix 80,128 rows: v5 bracket +0.29%, exact (2026-10-18)

Lane B, `packet114-v5-B`, 09:39–09:47 UTC, one model load, A/B/A/B/A on the packet 103 line, all 13 exact, control drift 0.09%. The candidate N = 80,128 rows (from 91,392) was **preregistered before any device run** on a fixed non-benchmark corpus (99.0142% token coverage; packet 56's retained rule: N never chosen from benchmark prompts, outputs, acceptance or timing).

| View | Rate | Draft acceptance |
| --- | ---: | ---: |
| control 1 (91,392) | 57.310 | 0.78543 |
| **candidate 1 (80,128)** | **57.513** | 0.78281 |
| control 2 | 57.256 | 0.78543 |
| **candidate 2** | **57.478** | 0.78281 |
| control 3 | 57.304 | 0.78543 |

Strict candidate/control ratio **1.00293 (+0.29%)**; both candidates faster than all controls. Acceptance falls by 0.26 points (4 hits out of 1,524 guesses), and the shorter head more than repays it. Below the +0.5% single-lever bar (packet's own `candidate_accepted=false`), but **eligible** under the coordinator's combined-candidate rule (faster than every control on its exact bracket, no lane-A loss) for stacking into the next bundle with packet 111's fusion + head split. Any submission that includes it must disclose the preregistered prefix rule.

Evidence: `experiments/own-xpu-runtime/stage2/packet114-draft-prefix/evidence/p114-v5-B/bracket-summary.json`.
