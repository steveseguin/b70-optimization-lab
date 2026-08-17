# Qwen3.8 27B Q8 TP2 exact ESIMD DP4A row kernel

Date: 2026-08-16

Status: closed; exact but `-0.699%` slower in a position-balanced TP2 screen.

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

The candidate was routed through standalone, fused pair, and fused triple
launches. The recurrent quad retained the accepted SG16 implementation because
its fused body calls `log1p`, which cannot be called from a pure ESIMD kernel in
this compiler path. These three routed families were live on both GPUs and are
the Q8 matrix-vector paths relevant to the measured decode.

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

## Implementation history

The first implementation kept the accepted SG16 kernel and called an ESIMD
SIMD16 row helper through `invoke_simd`. A minimal JIT program compiled and
returned the expected DP4A values. The complete BMG-G31 AOT image did not:

- putting the ESIMD helper in another translation unit left an unresolved
  external device symbol, even with the runtime door off;
- putting caller and helper in the same translation unit progressed further
  but failed the BMG AOT link on unresolved `__simd_func_call_helper`;
- adding `-fsycl-allow-func-ptr` globally broke unrelated templated device
  functions and was not a valid workaround.

The tested implementation therefore uses a direct ESIMD kernel: one SIMD16
work-item per matrix row, contiguous 256-byte weight and activation block
loads, four signed DP4As per logical lane, identical scale multiplication and
per-lane accumulation order, followed by the same explicit 8/4/2/1 FP32 tree
reduction as the accepted subgroup kernel. The runtime door retained its
experimental historical name, `GGML_SYCL_MMVQ_Q8_INVOKE_ESIMD=1`.

## Correctness proof

- treatment output for the fixed 75-token incident-retrospective prompt was
  byte-identical to the accepted control for all 128 generated tokens;
- the normal candidate reported standalone, pair, and triple liveness on both
  devices and `VERIFY_MISMATCH=0`;
- `GGML_SYCL_MMVQ_Q8_INVOKE_ESIMD_POISON=1` repeats the third weight vector in
  the fourth DP4A of the first block group; this changed the generated output,
  proving that the exact normal result exercised the candidate;
- the host remained healthy, with no Xe fault/reset/hang after testing.

The full 12-prompt promotion gate was not run because the performance screen
was decisively negative. This is a quality-exact smoke result, not a promoted
quality claim.

## Position-balanced performance

Same candidate binary, fresh process per arm, order `control, treatment,
treatment, control`, `llama-bench -p 64 -n 256 -r 3`, TP2 `SYCL0/SYCL1`, equal
split, Q8 target-only, F16 KV, flash attention, `b1024/ub256`:

| Position | Arm | Decode tok/s |
| ---: | --- | ---: |
| 1 | control | 36.728555 |
| 2 | direct ESIMD | 36.469295 |
| 3 | direct ESIMD | 36.475615 |
| 4 | control | 36.729824 |

- control mean: `36.7291895 tok/s`
- treatment mean: `36.4724550 tok/s`
- relative delta: `-0.6990%`

Prompt evaluation was also slightly slower (`381.52` versus `382.62 tok/s`,
approximately `-0.29%`). The simpler launch geometry and block loads did not
offset loss of the accepted subgroup kernel's scheduling/occupancy behavior.
Do not promote or rerun this direct row mapping unchanged.

## Reproduction artifacts

- structured summary:
  [`../data/2026-08-16-q8-direct-esimd-dp4a-negative.json`](../data/2026-08-16-q8-direct-esimd-dp4a-negative.json)
- incremental patch against the accepted Q8 source stack:
  [`../patches/q8-direct-esimd-dp4a-negative-20260816.diff`](../patches/q8-direct-esimd-dp4a-negative-20260816.diff)
- incremental patch SHA-256:
  `bd55bb56fa600c722c744d26aa4d363ce01509bf3700feed2222f02414b37618`
- local candidate source:
  `/mnt/fast-ai/src/llama.cpp-q38-q8-invoke-esimd-dp4a`
- local build:
  `build-sycl-aot-bmg-g31-invoke`
- candidate `libggml-sycl.so.0.19.0` SHA-256:
  `2127153e76559f26ac34337d435d32f3fc5cdcff7ca90d250fabbe9f954691f8`
- `llama-bench` SHA-256:
  `2205486e05dfda26395c496751919d24480f67bb56026409859dced821ca54ee`
