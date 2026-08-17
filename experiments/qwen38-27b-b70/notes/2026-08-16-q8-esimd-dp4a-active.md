# Qwen3.8 27B Q8 TP2 exact ESIMD DP4A row kernel

Date: 2026-08-16

Status: active on the two-ASRock-B70 reference host; do not duplicate unchanged.

## Source audit and hypothesis

Current upstream llama.cpp `4df29be4f4c3673f428170fda944a5b19f743bb8`
contains ESIMD DMMV kernels for reordered Q3_K, Q4_K, and Q6_K. Those kernels
block-load weights and activations but dequantize into FP32 FMA chains. They are
not directly suitable for the lab's no-quality-loss Q8 lane because they change
the integer-dot and FP32 reduction structure. No public Q8 ESIMD implementation
was found in the current upstream tree or open SYCL pull requests.

The accepted reordered Q8 kernel has a stronger exact mapping opportunity. One
SG16 row iteration consumes eight contiguous 32-byte weight blocks and the same
eight contiguous Q8_1 activation blocks. Each logical lane performs four signed
DP4As, scales one integer subtotal, accumulates every eighth block, and then
participates in an XOR 8/4/2/1 FP32 reduction. An ESIMD SIMD16 work-item can
express exactly that mapping with 256-byte block loads, four vector DP4As, the
same per-lane accumulation order, and an explicit XOR reduction.

The candidate is worthwhile only if the shared row body is routed through all
accepted decode launch shapes: standalone, fused pair, fused triple, and the
processed recurrent quad. A standalone-only port is considered structurally
inert and must not proceed to a long build.

## Contract

- same accepted Qwen3.8 Q8_0 model, TP2 target-only flags, selector, split,
  F16 KV, flash attention, and batch shape;
- isolated source and build directories; one same-binary runtime door;
- preserve the current Q8 integer DP4A order, per-lane block order, scale
  expression, and XOR reduction order;
- retain the ordinary SYCL SG16 body as mode 0 and as fallback for shapes that
  do not satisfy the ESIMD block/tail contract;
- first prove all four launch families are live and pass a poison/reach control;
- require exact backend-output comparison before endpoint timing;
- promote only after a position-balanced gain, complete cache-zero suite,
  exact output hashes, semantic canaries, long-context needle, and clean GPU
  health audit.

The build remains limited to two jobs with an 8 GiB hard host-memory cap. Any
compiler/device fault or output mismatch closes the arm unless the cause is a
mechanically repairable implementation error with an explicit oracle.
