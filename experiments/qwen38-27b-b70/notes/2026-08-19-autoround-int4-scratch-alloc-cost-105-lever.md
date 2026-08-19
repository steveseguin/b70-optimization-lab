# Quantifying the 105 lever: GDN scratch allocation cost measured

Date: 2026-08-19
Author: second-host agent (bounded XPU microbenchmark, no model load)

## Motivation

97bb161a5 states reaching 105 tok/s needs the persistent GDN scratch fixed
properly instead of disabled. This note puts numbers on that claim.

## Capability note

This host can run small XPU microbenchmarks safely under a user-scope memory
cap (`systemd-run --user --scope -p MemoryMax=8G`): no model load, <1 GB host
footprint, no desktop impact. Verified with a matmul probe and this benchmark.
Full-server launches remain prohibited.

## Measurement

Script: `experiments/qwen38-27b-b70/scripts/gdn-scratch-alloc-microbench.py`
Data: `experiments/qwen38-27b-b70/data/2026-08-19-gdn-scratch-alloc-microbench.json`

Exact TP2/MTP5 scratch shapes (k=5 → 6 verifier rows, 1 request, 48 GDN
layers): 12 buffers ≈ 250 KB total, so the cost is pure allocator overhead.
Steady-state medians, 1000 steps after 200 warmup:

| pattern | ms/step | meaning |
|---|---|---|
| empty-per-call | 0.926 | submitted 101.922 record lane (PERSISTENT_SCRATCH=0) |
| zeros-per-call | 2.435 | naive alternative — 2.6× WORSE; do not adopt |
| cached (zero once, reuse) | 0.007 | the 0ab8205 fix lane |

CPU control at identical shapes: 0.876 ms/step — about 93% of the Python-side
measurement is interpreter dispatch, not allocator work. The C++ `torch::empty`
cost in the real lane is therefore lower than 0.93 ms/step; honest bound is
roughly 0.3–0.9 ms/step.

## Projection against the 101.922 record

Tokens/step at MTP5 ≈ 1 + Σ per-position acceptance. MTP3 positions measured
[0.84, 0.65, 0.48]; extrapolated decay gives pos4 ≈ 0.36, pos5 ≈ 0.27 →
≈ 3.6 tok/step → ≈ 28 ms/step.

- scratch fix alone: +0.9 to +3.0 tok/s → **103–105, marginal**
- rerank K=2 (audited, ready): +0.1–0.2 tok/step from repairing position-1/2
  near-misses → **+3 to +6 tok/s stacked**

Conclusion: the scratch fix is necessary but likely not sufficient for 105 on
its own; scratch fix + rerank K=2 stacks to an estimated 106–109. Both items
are execution-ready for the measuring host (build 0ab8205 with normal
provenance, then strict A/B; rerank screen per its audit note).

## Anti-validated

Per-call `torch::zeros` as a "fix" would cost 2.44 ms/step (≈ −7 tok/s vs the
record). Zero-init is only safe at cache-creation time, exactly as 0ab8205
does. Recorded so nobody retries the per-call variant.
