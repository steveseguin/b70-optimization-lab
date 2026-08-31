# Qwen3.8 medium-prefill projection repairs D53 result

D53 passed its complete causal determinism screen.

- Four fresh TP1 processes produced the same complete 64-layer trace byte for
  byte (`af330c15...a2fe`).
- Every decoder input, hidden output, and residual at the M=71 prefill boundary
  was bit-identical.
- All four complete 64-token responses were token-identical, with no first
  difference.
- Prefix caching was disabled, cached tokens were zero, and each process used a
  separate cache directory.

This is the first end-to-end internal determinism pass after combining targeted
M=512 repairs for GDN projections, dense-MLP down projections, and
full-attention QKV/output projections. The branch excludes decode widths. D53
was a synchronized, single-prompt causal screen; it authorizes a strict
varied-prompt qualification but is not itself a publishable speed or quality
claim.
