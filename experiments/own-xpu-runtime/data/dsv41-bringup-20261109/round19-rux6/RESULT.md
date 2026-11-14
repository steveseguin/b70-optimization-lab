# rux6-1 speed A/B (rx6ab, 2026-11-13 19:39-20:05, uncapped cards)

Binary `rux6/bin/own_run_v41_rux6` (tp110 sources 0fe63f831 + rux6-1: prompt-block routed-expert launches with x
prefetches, `OWN_RUX6`). Traces with OWN_RUX6=1 identical (g1: prompt-1 at 64 / 256, 3K at 64 / 256 / px-512). A/B in the
production prompt mode (px-512 + copy engine), unprofiled, alternated; every answer the same as the references.

| run | OWN_RUX6=0 | OWN_RUX6=1 |
|---|---|---|
| 3K read (256 answers) | 4.87 / 4.78 s | 4.72 / 4.73 s (about -2 %) |
| 10K read (64 answers) | 15.71 s | 15.61 s (-0.6 %) |

The bench's per-slot gains (-12 to -20 % per expert slot at 512 tokens, README section 2) mostly do not reach the read
time: with two halves in flight the expert kernels are not the whole critical path. Small but exact: candidate for the
next build's defaults.
