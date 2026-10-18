# Packet 128b sampled in-engine budget: two measured critical-path costs (2026-10-18)

Lane B, `p128b-attribution-B-a` 13:22–13:30 UTC, bundle 7 line (packet 124c selection), tokens 9–16 of each request instrumented, all 48 layers, both ranks, 84 complete cycles, all exact. Throughput 51.475 tok/s (0.888 of 58.0): the packet's ≥ 0.90 overhead gate fails, so its own ranking is withheld; the class table is used as direction only.

Per hit cycle (mean / median ms):
- **Rank 1 `wait.head.suffix` 1.62 / 1.23** (misses 1.47 / 1.08): rank 1 waits for rank 0's head-suffix rows, which rank 0 computes (0.29 ms) only after its own speculative half (packet 105b design). This explains why the head split realised only +0.37% instead of the modelled +1.07%, and why moving more rows/layers to rank 0 lost (packets 127, 120).
- **Rank 0 `snapshot_capture` 0.52** on every cycle (rollback snapshot), on a near-critical rank.
- Largest compute classes per rank (both ranks similar): expsgate 1.44–1.46, gdn.qkv 1.18–1.20, attention 1.13, expsdown 0.93–0.94, gdn.z 0.71, route 0.54–0.55, router 0.53, hc.a/f.gate 0.53 each, gdn.recurrence 0.45–0.47, qsa.qgate 0.46, shexpdown 0.35; rank 1 head prefix 1.17. Host command gaps: rank 0 1.88, rank 1 4.09 mean (0.02 median).

Briefed: packet 130 (compute the suffix as soon as the hidden arrives: high-priority queue or chunked interleave, exact) and packet 131 (double-buffered state instead of the per-cycle snapshot copy, exact).

Evidence: `experiments/own-xpu-runtime/stage2/packet128b-attribution/BUDGET.md`.
