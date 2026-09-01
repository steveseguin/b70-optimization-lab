# Qwen3.8 FP8 TP2 AsyncTP PR #52683 screen

Status: **closed negative; no performance measurement**. The promoted
`774.394144 tok/s` c64 result is unchanged.

The lab ingested the four runtime files from vLLM PR #52683, authored by
`chaojun-zhang`, as a focused, hash-pinned patch in this repository. Its XPU
unit path passed all four two-card static/dynamic AG+GEMM and GEMM+RS cases.
That correctly establishes the contributed static-scale primitive, but not
compatibility with every FP8 checkpoint.

R14 failed before health because the image patched `/workspace/vllm` while
the `vllm` console script imported its installed site-package. R15 installed
the same four byte-identical files into the active import tree; the live
server then retained `sp` and `gemm_comms`, proving the integration fix.

Both R15 compile ranges reported zero AsyncTP replacements on both ranks. The
captured full-model graph explains why: that arm exposed per-token-group
activation quantization plus block-scaled weight scales, while PR #52683's XPU
path expected its static FP8 scale pattern. The later selected lab kernel is a
different W8A16 path: it skips activation quantization and consumes FP16/BF16
activations with block-FP8 weights and weight scales. PR #52683 supports neither
signature. The endpoint exited during
initial profiling after compilation and before any benchmark request.

This is therefore neither a speedup nor a measured regression. Extending the
idea to block-scaled Qwen is a new implementation project and must receive its
own unit tests, preregistration, and output/quality gates. The exact structured
boundary is in
[`2026-08-26-qwen38-fp8-tp2-asynctp-pr52683-r14-r15-result.json`](../data/2026-08-26-qwen38-fp8-tp2-asynctp-pr52683-r14-r15-result.json).
