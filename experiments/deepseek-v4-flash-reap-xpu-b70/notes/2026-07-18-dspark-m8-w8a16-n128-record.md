# DSpark M=8 W8A16 + N128 Record

Date: **2026-07-18**

Status: **promoted TP4+EP single-session, target-verified record**

## Outcome

Bundling selective M=8 W8A16 dense projections with the Xe2 N128 routed-
MXFP4 tile raises the unchanged K160/DSpark7 endpoint to **78.288267 tok/s**.
Three independent strict-suite medians are **78.288267 / 74.410268 /
76.937587 tok/s**; their median is **76.937587 tok/s**. The headline improves
by 6.781459 tok/s (9.48%) over the preceding 71.506808 record, while the
median-of-three improves by 6.688566 tok/s (9.52%).

| Strict suite | Median tok/s | p10 tok/s | Full after-TTFT tok/s | Wall tok/s | TTFT ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| screen | **78.288267** | 65.520512 | 77.548055 | 63.059722 | 371.945994 |
| confirmation | 74.410268 | 66.684304 | 77.119361 | 61.949273 | 341.923451 |
| third | 76.937587 | 71.313438 | 75.695078 | 60.656815 | 348.636241 |

All 36 realistic requests were unique, fresh, and reported
`cached_tokens=0`. Four ordered exact-output canary suites pass 24/24 before,
between, and after the performance suites, including the changed-input
`1073 -> 437 -> 1073` replay guard. This is one active generation, not
aggregate throughput. The K160 target remains unchanged and verifies accepted
DSpark tokens at M=8.

LocalMaxxing approved the result as `cmrqlp9je05thlg01q4igkk0x`.

## Why the bundle works

The target M=8 eager trace put dense GEMM at 11.818190 ms/cycle and routed
MXFP4 at 7.988468 ms/cycle. The four selected block-FP8 projection families
were still taking the W8A8 path at M=8: quantize BF16 activations to FP8, then
run the FP8 GEMM. Direct oneDNN W8A16 consumes BF16 activations and eliminates
that quantization boundary.

Across all four B70s, the four production shapes project **3.168-3.549 ms**
saved per 43 layers at M=8. Every shape wins on every card. The compatible
N128 routed-MXFP4 policy adds another **0.464-0.562 ms** projected saving; N32
is noise or a regression and remains rejected.

## Arithmetic and quality boundary

Unlike the M=8 compressor BMM, oneDNN's batched W8A16 reduction is not bitwise
row-invariant against eight separate M=1 calls. Over four shapes and 40
changing epochs, the maximum observed BF16 difference is 0.001953125-
0.0078125 with only 75-292 mismatching elements accumulated per shape. This
candidate is therefore not described as a bitwise target-arithmetic identity.

The endpoint was promoted only after the real quality and replay gates passed:
four ordered canary suites, 36 unpredictable realistic responses, cache-zero
enforcement, and unchanged target verification. Preserve this distinction in
future comparisons; a microbenchmark speedup alone was not the authority.

## Identity and evidence

- target: `0xSero/DeepSeek-V4-Flash-180B` revision
  `7c360e1cd4a5168099dbc54d16d929bf6df04990`;
- draft: `deepseek-ai/DeepSeek-V4-Flash` revision
  `aa22cb07426656189b2573b8e77a9b7333b8ae0f`;
- vLLM: `1f6d6be49c57a2d5b71c6ea4926d4b01ca612254`;
- XPU kernels: `0b99fc5360141d4dd6174fb15f30ec80c74c4d47`;
- oneCCL: `48fda4f0e074db005596d6899d5227d3f0316c12`;
- topology: four B70s, TP4+EP, concurrency 1;
- target graph: PIECEWISE; draft graph: breakable PIECEWISE M=7;
- target verifier: fixed M=8;
- endpoint artifact:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-m8-w8a16-n128-candidate-20260718T2130Z`;
- dense gates:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/fp8-dense-m8-w8a16-card{0,1,2,3}-20260718.json`;
- row-invariance gates:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/w8a16-m8-row-invariance-card{0,1,2,3}-20260718.json`;
- MXFP4 gates:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/mxfp4-m8-policy-{32,128}-card{0,1,2,3}-20260718.json`.

Launch the preceding record with these additional selectors:

```bash
VLLM_XPU_V4_COMPRESSOR_BATCHED_EXACT_MAX_M=8 \
VLLM_XPU_V4_BLOCK_FP8_W8A16_MAX_M=8 \
VLLM_XPU_MXFP4_SMALL_M_N=128 \
DSPARK_GRAPH_MODE=piecewise \
DSPARK_DRAFT_GRAPH_MODE=piecewise \
DSPARK_SPEC_TOKENS=7 \
VLLM_XPU_DSPARK_EXACT_QUERY_CAPTURE=1 \
VLLM_XPU_GREEDY_FUSED_REJECTION=1 \
VLLM_XPU_DSPARK_FIXED_M7_TARGET_INPUTS=1 \
VLLM_XPU_DSPARK_PERSISTENT_MARKOV=1 \
VLLM_XPU_DSPARK_REPLICATED_MARKOV_W1=1 \
experiments/deepseek-v4-flash-reap-xpu-b70/scripts/serve-k160-dspark-candidate.sh
```

## Decision

Promote M=8 selective W8A16 and MXFP4 N128 together. Keep N32 rejected. The
next profile must use this post-change identity; the former M=8 dense estimate
is no longer current. Remaining work should attack the post-change routed
MXFP4 implementation, MHC/attention, or draft-side cycle rather than retuning
the eliminated activation-quantization boundary.
