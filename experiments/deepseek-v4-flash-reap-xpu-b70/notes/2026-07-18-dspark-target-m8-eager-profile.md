# DSpark Target M=8 Eager Shape Profile

Date: **2026-07-18**

Status: **diagnostic complete; one dominant family promoted afterward**

## Scope and caveats

This is an eager, profiler-instrumented twin of the 67.501117 tok/s DSpark7
W1-replication identity. It is not endpoint throughput evidence. The profile
retains 23 target-forward calls per rank after dropping the first call and
associates device kernels to `xpu_v2: target_forward` with each event's host
submission timestamp.

Kineto reports impossible oneCCL device durations (278-354 ms/cycle) on this
stack. Those collective values are timeline-distorted and excluded. Host
target-forward duration is also heavily perturbed by eager execution and the
profiler. Only noncollective device attribution is used below.

Raw evidence:

`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-replicated-w1-target-eager-profile-20260718T1930Z`

Source identity: vLLM `f7734caed`, XPU kernels `0b99fc536`, oneCCL
`48fda4f0e`; target/draft graph replay was intentionally disabled.

## Target-forward attribution

Cross-rank mean noncollective work is 30.90-31.53 ms/cycle. The dominant
families are:

| Family | Mean ms/cycle |
| --- | ---: |
| dense `gemm_kernel` | 11.818190 |
| routed MXFP4 MoE | 7.988468 |
| other noncollective | 4.368700 |
| native MHC post/pre | 2.809673 |
| sparse QK/LSE | 2.023192 |
| sparse PV | 0.995041 |
| router radix select | 0.575345 |
| router radix sort | 0.484849 |
| routed gather | 0.165180 |

Dense shapes were correlated back to CPU operator input dimensions. The two
largest entries were the row-exact compressor projections:

| Operator/shape | Calls/cycle | Mean ms/cycle |
| --- | ---: | ---: |
| BF16/FP32-out `mm`, `[1,4096] x [4096,2048]` | 165.424 | 2.255027 |
| FP8, `[8,4096] x [4096,1536]` | 42.304 | 1.570863 |
| FP8, `[8,2048] x [2048,4096]` | 42.359 | 1.531246 |
| FP8, `[8,4096] x [4096,1024]` | 42.337 | 1.499834 |
| BF16 BMM, `[2,8,4096] x [2,4096,1024]` | 42.348 | 1.466041 |
| FP8, `[8,1024] x [1024,8192]` | 42.337 | 1.188746 |
| BF16/FP32-out `mm`, `[1,4096] x [4096,1024]` | 157.641 | 1.080416 |
| BF16 router, `[8,4096] x [4096,160]` | 42.337 | 0.524741 |
| FP8, `[8,512] x [512,4096]` | 42.337 | 0.521461 |

The M=1 counts are intentional: exact target verification decomposed every M=8
compressor into independent rows. That observation directly produced the
exact M=8 strided-batch compressor change, subsequently promoted at 71.506808
tok/s. After that promotion, routed MXFP4 and the remaining M=8 FP8/BF16 dense
families become the next noncollective target scopes.
