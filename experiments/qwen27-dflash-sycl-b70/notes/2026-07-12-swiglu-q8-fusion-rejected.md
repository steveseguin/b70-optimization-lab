# 2026-07-12 SwiGLU + Q8 fusion rejected

An opt-in `GGML_SYCL_FUSE_SWIGLU_Q8` experiment computed SwiGLU directly into
the Q8_1 input consumed by Q4_0 down projections. It matched the packed GLU
source layout and removed the standalone SwiGLU launch for the eligible dense
layers.

The three-repetition AOT no-spec microbenchmark improved only from `26.4575`
to `26.6171 tok/s` (+0.60%). More importantly, deterministic generation did
not preserve output. The control produced the expected 128-token Rayleigh
scattering answer; the fused run stopped after five tokens with `The \n\n\n`.
Adding an explicit volatile F32 rounding boundary after SiLU did not repair
the divergence.

This lane is rejected and must remain default-off. It must not be combined
with headline or correctness runs. The experiment shows that directly
reconstructing the backend's packed GLU-to-Q8 layout needs a tensor-level
golden comparison before any further performance work; end-to-end greedy
parity is not sufficient for debugging the first bad value.

The source experiment remains guarded in the working tree so the failed
approach is not silently rediscovered. A future retry should first add a
backend operation test comparing the full intermediate Q8 bytes for standard
and reordered layouts.
