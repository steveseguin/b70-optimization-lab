# Qwen3.8 Q8 fused MMVQ/SwiGLU experiment

Status: **closed, performance negative; do not enable in the accepted recipe**.

## Hypothesis

The accepted decode graph launches adjacent Q8 gate/up MMVQs and then a
SwiGLU producer. The experiment computed both dot products in one device-local
kernel and wrote only the sole SwiGLU output. It retained the accepted
reordered-Q8 block walk, two-chain integer DP4A body, FP32 accumulation and
subgroup reduction, then used the existing FP32 SwiGLU expression. The graph
door was strict, decode-only, exact-shape gated, and default-off as
`GGML_SYCL_FUSED_MMVQ_SWIGLU_Q8=1`.

Version 1 removed the gate/up intermediates and GLU launch but accidentally
lost the accepted SwiGLU-to-Q8 producer handoff. It increased activation
quantization launches from `3,084` to `101,516` and measured `36.690636`
versus `37.019616 tok/s` (`-0.889%`). This was useful mechanism evidence, not
a candidate result.

Version 2 assigned one 32-subgroup workgroup to each 32-value Q8_1 block. It
stored the already-rounded SwiGLU values in 128 bytes of local memory, then
repeated the accepted producer's two-values-per-lane sum, max, subgroup
reduction, scale and rounding order. This restored the downstream reordered
Q8_1 handoff without a separate quantization launch.

## Result

A same-binary, position-balanced `OFF-ON-ON-OFF` bracket used Qwen3.8 Q8_0,
equal TP2, F16 KV, FlashAttention, `p64/n256/r3`, `b1024/ub256`, eight host
threads and poll 50.

| Arm | Process means (tok/s) | Pooled mean |
| --- | --- | ---: |
| accepted pair + SwiGLU/Q8 producer | `36.816490`, `36.790260` | **`36.803375`** |
| fused MMVQ + SwiGLU/Q8 producer | `36.835368`, `36.605786` | **`36.720577`** |

The candidate delta is **`-0.224974%`**. Both arms reported `3,084`
quantization launches and `VERIFY_MISMATCH=0`. OFF reported `98,432` legacy
MMVQ-pair hits; ON reported `98,432` fused MMVQ/SwiGLU hits and `98,432`
SwiGLU Q8 prefills. The one-token mechanism smoke also passed, both GPUs
remained visible, and no new Xe fault/reset appeared in the checked kernel
window.

The fusion is therefore numerically credible but performance-neutral/slightly
negative. It did not receive an endpoint or semantic run and must not replace
the accepted target-only recipe.

## Reproduce the source

The incremental artifact applies on top of the accepted DP4A2 source delta:

```bash
base64 -d \
  experiments/qwen38-27b-b70/patches/q8-fused-mmvq-swiglu-v2-negative-20260816.diff.gz.b64 \
  | gzip -dc > /tmp/q8-fused-mmvq-swiglu-v2.patch
sha256sum /tmp/q8-fused-mmvq-swiglu-v2.patch
git apply --check /tmp/q8-fused-mmvq-swiglu-v2.patch
git apply /tmp/q8-fused-mmvq-swiglu-v2.patch
```

The decoded SHA-256 must be
`6bdb7691bb4f6133033a7a43971fd67884c69f92cd96463d19ee27c51bba479c`.
The structured result and raw-log hashes are in
[`2026-08-16-q8-fused-mmvq-swiglu-negative.json`](../data/2026-08-16-q8-fused-mmvq-swiglu-negative.json).
Raw logs remain under
`/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260816-fused-swiglu/`.

## Decision

Keep the accepted adjacent MMVQ pair plus SwiGLU/Q8 producer. The result also
shows why deleting small global intermediates is insufficient at the current
`~86%` aggregate HBM roofline efficiency: a new design must reduce streamed
weight or cross-bridge traffic without changing the Q8 target values.
