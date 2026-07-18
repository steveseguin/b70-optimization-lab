# M=8 Router Fusion Record And Post-Record Closures

Date: **2026-07-18**

Status: **promoted TP4+EP single-session, target-verified record**

## Outcome

The exact native M=8 router raises the unchanged K160/DSpark7 endpoint to a
new **80.163578 tok/s** strict-suite record. The three independent medians are
**75.845916 / 77.572536 / 80.163578 tok/s**; their median is **77.572536
tok/s**, up from 76.937587 for the preceding record. All 36 realistic requests
reported `cached_tokens=0`. Four ordered six-case canary suites passed 24/24,
including every `1073 -> 437 -> 1073` changed-input replay guard.

This is one active generation, not aggregate throughput. The unchanged K160
target verifies DSpark7 accepted tokens at fixed M=8. LocalMaxxing approved
the result as `cmrqp2uoa05ublg01lh6yluj8`.

| Strict suite | Median tok/s | p10 tok/s | Full after-TTFT tok/s | Wall tok/s | TTFT ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| screen | 75.845916 | 67.247932 | 78.577462 | 62.137845 | 361.861398 |
| confirmation | 77.572536 | 70.011342 | 78.154689 | 62.787194 | 334.854939 |
| third | **80.163578** | 68.282387 | 79.949524 | 62.996650 | 329.957940 |

## What changed

The standard router performed bias add, sorted top-k selection, score gather,
K=6 normalization, and routed scaling as separate graph operations. The
existing native SIMD16 router already fused this boundary for M=2. Extending
the same fixed K160 contract to M=8 replaces the complete sequence with one
submission in each of 40 normal MoE layers.

The important correctness issue was not top-k selection; IDs were exact from
the first M=8 attempt. FP32 normalized weights differed by one ULP because
PyTorch XPU uses a width-dependent K=6 reduction tree. Narrow M=2 reduces
adjacent pairs. Wide M=8 first combines lanes `(0,4)` and `(1,5)`, then adds
that half to `(2,3)`. Matching that tree and retaining the existing
reciprocal-plus-FMA residual correction made both IDs and weights bit-exact.

Across all four B70s, M=8 passed 40/40 changing eager epochs and 32/32 changing
graph epochs per card with zero ID or weight mismatches. Captured projected
savings were **1.205-1.222 ms per 40-layer target cycle**. M=2 remained exact
and saved 1.126 ms in the final regression gate.

M=4 is deliberately not enabled. Its IDs are exact, but the best tested
wide-tree quotient matched only 14/40 eager and 8/32 graph epochs; direct
division fell to 0/40 and 0/32. The production wrapper and vLLM selector accept
only the proven M=2 and M=8 contracts, so fixed M=7 draft work remains on the
canonical path.

## Post-record profile and rejected lanes

The post-W8A16/N128 eager target profile measured noncollective device work at
27.03-27.55 ms/cycle by rank. Rank 0 attributed 7.192944 ms to routed MXFP4,
6.508915 ms to dense GEMM, 3.537847 ms to sparse QK/LSE, 2.801384 ms to MHC,
1.777749 ms to PV, 0.574555 ms to radix selection, and 0.485149 ms to sort.
This profile selected the router boundary and remains the current target-side
priority map; profiler-distorted collectives are excluded.

Two plausible component wins were rejected at the endpoint boundary:

- M=8 route-direct compact MXFP4 was exact on every card, but realistic route
  distributions lost 1.03-1.11 ms per 43 layers and six-local patterns lost
  3.22-3.76 ms. Only the artificial all-remote case won about 0.16 ms. It was
  reverted before endpoint testing.
- Width-aware split-FP8 attention geometry (`4/8/4` versus `4/16/4`) passed
  768/768 changed graph cases per card and projected 2.54-2.59 ms component
  savings. The clean endpoint nevertheless regressed to 72.460375 tok/s
  (another retry was 73.399750), demonstrating worse complete-graph occupancy
  or overlap. It remains reverted and default-off.

## Identity and evidence

- vLLM: `db1863c7994fd79dc6dd860b64f9748af0eb7f96`;
- XPU kernels: `6cad2518d700cbe02906b4e46fef0bbaec053cc1`;
- oneCCL: `48fda4f0e074db005596d6899d5227d3f0316c12`;
- endpoint: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-m8-router-fused-candidate-20260718T1815Z`;
- final router gates: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/router-norm-mwidth-final-20260718`;
- four-card M=8 gates: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/router-norm-mwidth-4card-20260718/card{0,1,2,3}-m8.json`;
- post-record profile: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-m8-w8a16-n128-target-eager-profile-20260718T2200Z`;
- route-direct rejection: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/mxfp4-m8-route-direct-compact-20260718`;
- attention gates: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/split-fp8-attn-mwidth-graph-gate-recordbaseline-20260718`;
- attention endpoint: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-m8-attn-geometry-xpubase-20260718T1750Z`.

Restore the record by adding `VLLM_XPU_V4_ROUTER_NORM_MAX_M=8` to the exact
preceding W8A16/N128 launch recipe.

## Decision

Promote exact native M=8 router normalization. Keep M=4, route-direct compact
MXFP4, and width-aware attention geometry rejected. The next target-side work
should attack routed MXFP4 without assuming all-remote routing, or fuse a
boundary whose isolated geometry survives full-graph occupancy. The draft-side
alternative remains a device-resident sampler/acceptance/commit transaction.
