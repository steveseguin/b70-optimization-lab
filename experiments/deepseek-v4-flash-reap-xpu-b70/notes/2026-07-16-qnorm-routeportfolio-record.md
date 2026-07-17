# QNorm-M2 + Route-Direct Portfolio Record

Date: **2026-07-16**

Status: **promoted target-verified record**

LocalMaxxing: **approved**, `cmrocpuhq029hlg01g3yzglko`

## Result

The frozen DeepSeek V4 Flash uniform-K160 TP4+EP, one-active-generation,
MTP1 lane reached **63.851301 tok/s** median for generated tokens 1-100 after
TTFT. P10 was **59.718212 tok/s**, mean was **63.285576 tok/s**, full-output
after-TTFT median was **63.433255 tok/s**, wall median was **53.223804 tok/s**,
and median TTFT was **334.099 ms**.

This exceeds the prior matching 4-GPU record of **63.349928 tok/s** by
**0.501373 tok/s (0.79%)** without changing the model, topology, speculative
depth, prompt policy, or target-verification semantics.

Primary evidence:

- candidate B1: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/qnorm-routeportfolio-candidate-b1-20260716T2235Z`;
- same-binary control A: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/qnorm-routeportfolio-control-a-20260716T2250Z`;
- record candidate B2: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/qnorm-routeportfolio-candidate-b2-20260716T2255Z`;
- four-card hardware gate and summary: `../data/qnorm-routeportfolio-20260716/`.

## Change

This was a predeclared portfolio of two independent M=2 verifier boundaries:

1. extend the already-promoted fused QNorm + RoPE + FP8 KV insertion path from
   M=1 to M=2;
2. select a fixed routed-MoE chain for the exact K160 verifier contract:

   `direct remap -> 12-slot N64 compact MXFP4 GEMM1 -> canonical clamp-at-10
   SwiGLU -> compact GEMM2 -> generic gather`.

The production selector is default-off and fail-closed under
`VLLM_XPU_V4_M2_ROUTE_DIRECT_COMPACT=1`. It requires the exact MXFP4/BF16,
M=2, hidden-4096, top-k-6, EP4, 160-global/40-local-expert contract and also
requires the already-promoted `VLLM_XPU_V4_M2_ROUTED_CLAMP_SILU=1` semantics.
All other rows and models retain the generic path.

Frozen source identity:

- vLLM: `4a6fd874725312c53883b1d53970af1d0eccfc3f`;
- XPU kernels: `18a44f440ca3ac2006d5ba19cd12ccca0a0c9982`;
- oneCCL: `48fda4f0e074db005596d6899d5227d3f0316c12`;
- `_xpu_C.abi3.so`: `afe32514bd508c5382495713c894d1b7173f6a170e3c21030c2baa171c201956`;
- `_moe_C.abi3.so`: `e9f3522bf74f3f3a068e9e83e4bc70272c6d9c3668bc725ead86b5bf364bcfe3`.

The measured XPU commit descends from the prototype branch and therefore
contains dormant experimental gather/activation variants. The enabled
production selector invokes only the chain listed above. Do not rewrite the
measured identity after the fact; a future cleanup transplant must be rebuilt
and requalified as a distinct binary.

## Gate accounting

The frozen standalone component gate was not weakened. The route-direct path
remained below its independent 0.50 ms/cycle requirement:

- card 0: 0.417416 ms/cycle conservative floor;
- card 1: 0.397270 ms/cycle;
- card 2: 0.412385 ms/cycle;
- card 3: 0.421553 ms/cycle.

It was admitted only as the previously declared non-overlapping portfolio with
the independently proven QNorm-M2 floor. The portfolio estimate was about
2.08 ms/cycle. No standalone `passed=true` claim is made for route-direct.

Hardware correctness passed:

- direct operations: **336/336 bitwise exact** changed-route/changed-input
  graph replays across four physical B70s;
- guarded production wrapper: **84/84 bitwise exact** graph replays on card 0;
- duplicate, cross-row-overlap, all-local, and all-remote route patterns were
  included.

## Same-binary service evidence

| Run | Median tok/s | p10 tok/s | Mean tok/s |
| --- | ---: | ---: | ---: |
| Candidate B1 | 62.515661 | 59.939429 | 62.935587 |
| Control A | 61.717893 | 58.533143 | 61.889352 |
| Candidate B2 | **63.851301** | **59.718212** | **63.285576** |

B2 is **2.133408 tok/s (3.46%)** above the same-binary control. B1 was also
positive over control by 0.797768 tok/s (1.29%), although its absolute score
did not exceed the prior record. All 36 realistic requests passed the fixed
fresh-response gate and reported `cached_tokens=0`.

## Correctness and the invalid max-8 diagnostic

Seventy ordered exact capture suites pass **70/70**, including the historical
collective epoch-sensitive positions 28 and 58. Every qualifying canary row is
cached-zero.

An initial operator command accidentally used `max_tokens=8` instead of the
frozen `max_tokens=32` canary contract. Five rows were exact; strict JSON was
truncated by its final closing brace. That capture is preserved under the
`exact-invalid-max8-01` prefix and is classified as invalid harness evidence,
not as a model failure or a qualifying pass.

## Interpretation

This is a real but small record. Microbench savings translated incompletely to
the full speculative cycle, and service variance remains large enough that the
paired B-A-B design was essential. The result supports keeping the two M=2
boundaries together; it does not justify weakening sub-gates or adding the
previously measured-loss direct gather, routed activation, N128 policy, or
four-lane scheduler variants.

The next architectural work should return to exact cycle attribution and test
only boundaries with a conservative whole-cycle ceiling of at least 0.50 ms.
