# 2026-07-12 MMVQ + residual + RMSNorm + Q8 result

The guarded `GGML_SYCL_FUSE_MMVQ_ADD_RMS_Q8=1` lane recognizes the actual
Qwen decoder chain:

`MMVQ -> residual ADD -> RMS_NORM -> norm-weight MUL -> 1..3 MMVQ consumers`.

It reuses the skipped norm output allocation as fixed-address Q8_1 scratch,
computes RMSNorm, learned scaling, and Q8_1 production in one kernel, and
reuses that Q8 input across gate/up or Q/K/V consumers. No allocation occurs
inside graph capture. `GGML_SYCL_FUSE_MMVQ_ADD=1` is also required. Both flags
remain default-off.

## Validation

- Deterministic 128-token no-spec output hashes were exactly equal:
  `1bfa84aa271dd2c1a863f91b2dfd7d70adfb6a96a435d4f5837b221303216716`.
- The matched no-spec run was `26.5673` versus `26.0521 tok/s` (+1.98%).
- Three-repetition `llama-bench` was `26.0278` versus `25.4870 tok/s`
  (+2.12%).
- Eight strict MTP3 suite runs crossed both flag states over all four B70s.
  Every run passed the realistic gate and reported all prompt-cache counts
  zero. Combined medians averaged `48.806` on versus `47.999 tok/s` off
  (+1.68%).

This is a verified building block, not the requested performance outcome. It
removes real intermediate traffic and launches, but MTP remains near 49 tok/s.
The flag stays guarded while the fusion boundary is extended through SwiGLU
and down-input quantization.

Artifacts are the `parity-rmsq8-*`, `mtp3-rmsq8-crossover-*`, and
`mtp3-rmsq8-reverse-*` JSON files under
`data/qwen36-27b-mtp-gguf-q4-b70-baselines/`.
