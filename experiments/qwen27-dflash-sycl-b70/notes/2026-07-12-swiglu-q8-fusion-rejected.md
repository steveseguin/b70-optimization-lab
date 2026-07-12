# 2026-07-12 SwiGLU + Q8 fusion initial rejection and repair

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

The root cause was subsequently identified: when the down projection was also
fused with residual ADD, the physical ADD destination was used to match a
fusion state keyed by the logical MUL_MAT node. The fused quant branch was
therefore skipped and ordinary quantization read the skipped/uninitialized GLU
tensor. The graph loop then cleared the state as if fusion had occurred.

The repair passes the logical MUL_MAT identity separately from the physical
ADD output and restricts transparent metadata to exact identity
RESHAPE/VIEWs. After the repair, the same deterministic 128-token response is
exactly restored. A JIT three-repetition no-spec pair measured `26.6214` on
versus `26.4765 tok/s` off (+0.55%). The flag remains default-off pending AOT
MTP crossover validation; the initial broken results must not be used.

The failed result remains documented so the logical-vs-physical consumer bug
is not rediscovered. A backend byte test for packed/split, swapped, standard,
and reordered Q8 layouts is still required before default enablement.
