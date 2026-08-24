# Ornith 1.5 35B multi-row routed gate/up: fast, exactness-negative

Date: 2026-08-23

## Result

A multi-token extension of the accepted routed-expert gate/up/SWIGLU kernel
activated 2,800 times and improved a deterministic four-sequence low-level run
from `128.82` to `179.70 tok/s` (**+39.50%**). It was rejected because the
candidate transcript was not byte-identical to the same-binary flag-off
control. This patch must not be used in a validated package.

## Candidate

The existing one-token fusion shares Q8_1 input quantization between Ornith's
Q4_K routed gate and up projections and writes SWIGLU directly. The candidate
added an independent token dimension with:

- per-token strided top-8 route IDs;
- per-token Q8_1 input rows;
- per-token/expert output strides;
- the same reordered-Q4_K dot product and SWIGLU expression;
- a separate default-off door,
  `GGML_SYCL_FUSED_ORNITH_MOE_GATE_UP_MULTIROW=1`.

The real graph confirmed the expected shape. One traced batch used projection
`[512,8,16]`, input `[2048,1,16]`, and strided IDs `[8,16]` with byte strides
`[4,1024,...]`. The original zero-hit attempt had incorrectly required the ID
view to be contiguous; permitting its exact router-row stride produced all
2,800 expected hits.

Archived source patch:
`../patches/llamacpp-ornith15-multirow-moe-gate-up-exactness-negative-20260823.patch`
(SHA-256 `11f917406faf210f2b3807e20823ba06e079f49b52935815c83591a52dc64d90`).

## Decisive gate

Both arms used `llama-batched`, four fixed sequence IDs, unified KV, the same
prompt and seed, greedy temperature zero, and 276 generated tokens. The
flag-off control reproduced the established accepted transcript:

- control SHA-256:
  `1b50819cab9e15ac7e5219f05e8f76878686ded24b3a99ebde6616dad4b621f1`
- candidate SHA-256:
  `5b7fce0350dc30b263bbc466b62372d64755d2710b34e4cd37e8c2519bb1fff1`
- `cmp`: different

The change is semantically plausible text, but plausible output is not an
exactness proof. Unlike fresh HTTP-server nondeterminism, this low-level
control is repeatable and has already served as a byte-exact gate. The speed
result therefore identifies valuable headroom, not a shippable optimization.

## Disposition

Keep this as a negative research artifact. A future attempt must reproduce the
stock multi-row routed-expert arithmetic/order or establish a stronger bounded
numerical and quality gate before any promotion. Do not combine it with the
positive multi-row reduction/RMS patch merely to obtain a larger throughput
number.
