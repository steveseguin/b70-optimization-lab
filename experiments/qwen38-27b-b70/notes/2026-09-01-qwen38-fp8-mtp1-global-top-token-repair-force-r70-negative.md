# Qwen3.8 FP8 TP2 MTP1 R70: forced ordinary-M1 replay is insufficient

R70 raised the R69 repair margin to 100, forcing every eligible row through
ordinary M=1 oneDNN replay. The c2 output still diverged at the identical
`cache-c000` token 96. Therefore the 0.25 margin was not the main failure: an
ordinary M1 GEMM is not a sufficiently stable reference for this exact tie.

R71 replaces only the rare repair computation with vLLM's batch-invariant
dot-product implementation, the same implementation that made R65 exact when
applied to the entire target head. The normal head and draft-only INT4 path
remain fast; only globally ambiguous target rows pay the expensive repair.

Structured evidence is in
[`2026-09-01-qwen38-fp8-mtp1-global-top-token-repair-force-r70-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-global-top-token-repair-force-r70-result.json).
