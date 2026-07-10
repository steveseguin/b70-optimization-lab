# Qwen27 low-row W4A16 custom-kernel audit

Date: 2026-07-10

Status: source/timing audit; no implementation, endpoint result, or
LocalMaxxing submission.

## Question

Could one purpose-built Intel Xe2 W4A16 kernel remove at least `3 ms` from the
current approximately `40.26 ms` MTP3 verifier step, enough to materially help
the path toward `100 tok/s`?

## Current target-body calls

At four verifier rows, the 64-layer Qwen3.6 27B target makes 256 W4A16 calls:

| Layers | Projection | Shape `K -> N` |
| ---: | --- | ---: |
| 48 GDN | qkvz | `5120 -> 16384` |
| 48 GDN | output | `6144 -> 5120` |
| 64 | MLP gate+up | `5120 -> 34816` |
| 64 | MLP down | `17408 -> 5120` |
| 16 full attention | qkv+gate | `5120 -> 14336` |
| 16 full attention | output | `6144 -> 5120` |

The active path is:

```text
INCXPULinearMethod.apply
  -> torch.ops._xpu_C.int4_gemm_w4a16
  -> int4_gemm_w4a16
  -> oneDNN::dnnl_matmul_w4a16_int4
```

Inputs are contiguous BF16 `[4,K]`. The packed weights represent symmetric
group-128 INT4 `(u4 - 8) * scale`, with BF16 scales, FP32 accumulation, and
BF16 output. Relevant source:

```text
/home/steve/src/vllm/vllm/model_executor/layers/quantization/inc.py
/home/steve/src/vllm-xpu-kernels/csrc/xpu/onednn/onednn_matmul.cpp
/home/steve/src/vllm-xpu-kernels/csrc/xpu/onednn/int4_gemm_w4a16.h
```

## Closest credible boundary

The only design close to the threshold crosses a much larger boundary than the
failed backend swaps and pointwise wrappers: fuse GDN W4 qkvz, the adjacent
BF16 BA projection, and width-4 convolution/staging. A static Xe2 launch would
use 256 `M=4,Ntile=64,K=5120` qkvz workgroups plus two BA tiles, retain four
projected rows, emit q/k/v/z directly, and write `conv_pending` without
materializing `[4,16384]` qkvz or `[4,96]` BA intermediates.

That design would touch new Xe2 GDN files plus
`gdn_attn_interface.cpp`, `ops.h`, `torch_bindings.cpp`, `_xpu_ops.py`, and
`gdn_linear_attn.py`. It must preserve the mandatory BF16 per-product rounding
before FP32 convolution accumulation.

## Why it is not implemented now

Measured queue-level BA is only about `0.035-0.038 ms/layer`; prior stage work
is about `0.023 ms/layer`. Their combined theoretical removal is about
`0.061 ms` per GDN layer, or `2.93 ms/step` across 48 layers, before paying the
fused epilogue. The existing Xe2 W4 primitive also loses to oneDNN at the real
shapes. The proposal therefore starts below the required confidence threshold.

Reopen only if a real-weight, captured microbenchmark demonstrates a
lower-confidence-bound saving of at least `0.0625 ms/GDN`, preferably
`0.075 ms/GDN`, with exact stage/pending parity and the established recurrent
tolerances. DDTree's broad acceptance gain makes branch-aware GDN tree state
and verifier-row cost the higher-priority engineering lane.
