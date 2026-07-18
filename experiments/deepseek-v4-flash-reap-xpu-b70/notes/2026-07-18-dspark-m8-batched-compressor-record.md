# DSpark M=8 Batched-Compressor Record

Date: **2026-07-18**

Status: **promoted TP4+EP single-session target-verified record**

## Outcome

Extending the exact strided-batch compressor projection from M=2 to the
DSpark7 target verifier's M=8 width raises the unchanged K160 target to a new
strict-suite high of **71.506808 tok/s**. Three independent strict-suite
medians are **69.343725 / 71.506808 / 70.249021 tok/s**; their median is
**70.249021 tok/s**.

| Strict suite | Median tok/s | p10 tok/s | Mean tok/s | Full after-TTFT tok/s | Wall tok/s | TTFT ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| screen | 69.343725 | 58.538345 | 68.923427 | 65.131123 | 54.363748 | 355.340276 |
| confirmation | **71.506808** | 59.756583 | 70.169631 | 68.250367 | 57.566530 | 349.601738 |
| third | 70.249021 | 61.755874 | 68.487340 | 66.545507 | 55.849793 | 347.561435 |

All 36 realistic requests were unique, fresh, and reported
`cached_tokens=0`. Four ordered six-case exact suites pass before, between,
and after the performance suites: 24/24 requests, including the changed-input
`1073 -> 437 -> 1073` replay guard. This is one active generation, not
aggregate throughput. The target remains the same K160 model and verifies all
accepted DSpark tokens at M=8.

Relative to the preceding 67.501117 headline, the new high is +4.005691 tok/s
(+5.93%). The median-of-three stability result rises from 67.182469 to
70.249021 tok/s (+4.56%).

LocalMaxxing approved the result as `cmrql07qs05t4lg01p86jjybx`.

## Why it was slow

The compressor projections must match sequential target evaluation bit for
bit. A plain M=8 GEMM changes floating-point accumulation in general and was
therefore replaced by eight independent M=1 FP32-output GEMMs plus a
concatenation. The target trace measured those two families at 3.335443
ms/cycle in total:

- C4, `M8 x K4096 -> N2048`: 2.255027 ms/cycle;
- C128, `M8 x K4096 -> N1024`: 1.080416 ms/cycle.

The promoted M=2 path had already established a better exact formulation: use
one `torch.bmm` with each verifier row as a separate batch item and a
stride-zero expanded view of the same read-only weight. Generalizing that
formulation to M=8 preserves independent-row accumulation order while
removing seven GEMM submissions and the concatenation for every compressor.

## Four-card component gate

The real K160 layer-2 C4 and layer-3 C128 weights were tested independently on
all four B70s. Each card passes 40/40 changing eager comparisons and 40/40
fixed-address graph replays for both shapes, bit for bit against eight M=1
projections. The M=8 BMM is 5.93-7.03x faster in the microgate. Projected
41-layer savings are 12.463-13.378 ms/cycle before production graph overlap;
the endpoint result, not that isolated projection, is the promotion authority.

Component artifacts:

`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/compressor-m8-bmm-exact-card{0,1,2,3}-20260718.json`

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
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-xpu-compressor-m8-candidate-20260718T2030Z`;
- target eager shape trace:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-replicated-w1-target-eager-profile-20260718T1930Z`.

The new behavior is guarded by
`VLLM_XPU_V4_COMPRESSOR_BATCHED_EXACT_MAX_M=8`. Its default preserves the old
M=2 behavior; it is not silently enabled for unrelated widths.

Launch with the preceding DSpark7 record flags plus:

```bash
VLLM_XPU_V4_COMPRESSOR_BATCHED_EXACT_MAX_M=8 \
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

Promote M=8 batched exact compressor projections. Keep the ordinary plain M=8
GEMM rejected as a sequential-verifier oracle even though it matched the
sampled microgate inputs. The next target-side work should use the post-change
profile: routed MXFP4 and the remaining FP8/BF16 dense families, not the now
collapsed independent compressor submissions.
