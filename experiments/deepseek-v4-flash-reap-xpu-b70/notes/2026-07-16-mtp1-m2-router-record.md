# MTP1 M=2 Router Fusion Record

Date: **2026-07-16**

Status: **promoted target-verified record**

LocalMaxxing: **approved**, `cmrncv39w003ylg01hogleazo`

## Result

The frozen DeepSeek V4 Flash K160 TP4+EP, one-active-generation, MTP1 lane
reaches a new strict realistic-suite record of **63.349928 tok/s** median for
tokens 1-100 after TTFT, with **59.079885 tok/s p10**. An independent strict
screen reached **62.882999 tok/s** median and **59.017913 tok/s p10**. All 24
realistic requests report zero cached prompt tokens.

This is a single-session result. It is not aggregate throughput, prompt/KV
reuse, response reuse, history acceleration, or benchmark-specific routing.
The unchanged target model verifies every accepted MTP draft token.

Primary evidence:

- candidate: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/mtp1-m2-router-norm-candidate-20260716T0605Z`;
- same-build flag-off control: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/mtp1-m2-router-norm-control-20260716T0610Z`;
- four-card microgate: `../../../data/deepseek-v4-reap-m2-router-norm-20260716/`;
- eager-cycle profile that identified the boundary: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/mtp1-record-eager-cycle-profile-20260716T0550Z`.

The reusable trace summary is documented in
`2026-07-16-mtp1-eager-cycle-profile.md` and tracked as
`../data/eager-cycle-profile-20260716-summary.json`.

## Why the time was previously misidentified

The first reading of the eager trace assigned the repeated radix-select/sort
work to the Lightning Indexer. Exact operator-argument inspection disproved
that attribution: `aten::topk` receives a `[2,160]` FP32 tensor, requests
`k=6`, and runs 40 times per MTP1 verifier cycle. That is the ordinary target
MoE router for the two verifier rows. At the frozen 1K context, the C4
Lightning Indexer uses its full-selection bypass and does not run a top-k.

This correction mattered because optimizing the incorrectly named subsystem
would not remove the measured work. It also exposed a high-confidence fusion
boundary with a previously proven M=1 implementation and a simple exact M=2
contract.

## Change

XPU-kernel commit `d15ce87d07376be53ea2d6f7ae0262ab79f7cb7b`
generalizes the proven SIMD16 M=1 biased-top-k kernel to explicit row offsets
and adds `deepseek_m2_biased_topk_norm_out`. One submission launches two
independent workgroups for the two `[2,160]` verifier rows and produces the
final six expert IDs and normalized/scaled weights directly. It replaces the
generic bias add, radix top-k/sort, gather, sum, normalization, scaling, and
their intermediate traffic while preserving the original FP32 operation
order at the visible output boundary.

vLLM commit `4a6fd874725312c53883b1d53970af1d0eccfc3f` selects the kernel only for
the exact DeepSeek V4 contract. The selector is default-off and controlled by
`VLLM_XPU_V4_M2_ROUTER_NORM=1`; every other shape and model retains the generic
fallback.

## Four-card hardware gate

Each physical B70 was tested independently through `ZE_AFFINITY_MASK`; the
JSON files therefore report logical `xpu:0` inside each isolated process while
their filenames identify physical cards 0-3.

- M=2 changed-input eager: **160/160 bitwise exact** across four cards;
- M=2 changed-input graph replay: **128/128 bitwise exact**;
- generic graph path: **46.788-47.087 us/call**;
- fused graph path: **18.710-18.898 us/call**;
- projected savings over 40 normal routed layers:
  **1.123138-1.127542 ms/cycle**;
- generalized M=1 regression: **160/160 eager and 128/128 graph replays
  bitwise exact** across four cards.

## End-to-end evidence

| Run | Median tok/s | p10 tok/s | Mean tok/s |
| --- | ---: | ---: | ---: |
| Same-build flag-off control | 59.108299 | 56.380192 | 59.399110 |
| Candidate screen | 62.882999 | 59.017913 | 62.460085 |
| Candidate confirmation | **63.349928** | **59.079885** | **62.864699** |

The candidate screen is 6.39% above the same-build control and the confirmation
is 7.18% above it. The confirmation is 5.12% above the preceding 60.264242
tok/s record. Full-output after-TTFT median is 62.703233 tok/s, wall median is
52.971626 tok/s, and median TTFT is 332.735 ms.

Seventy ordered exact capture suites pass **70/70** after the strict suites,
including the former collective-epoch rollover positions 28 and 58. All exact
and realistic requests are cached-zero. Open-ended greedy output hashes retain
the already documented K160 cross-suite variance, so the promotion relies on
the strict correctness canaries, exact target verification, sustained replay,
and unchanged quality identity rather than claiming universal byte-for-byte
open-ended output identity.

## Why this is important

This is the first post-60 tok/s improvement whose isolated hardware savings
and same-build service delta agree at full-cycle scale. It validates the
method needed for the remaining work: profile exact operator shapes, fuse a
complete visible boundary, gate all four cards under graph replay, and require
a paired service control. It also moves the current frozen K160 system from
60.264242 to 63.349928 tok/s without changing the model, topology, speculative
depth, prompt policy, or target-verification semantics.

## Frozen identity

- model: `0xSero/DeepSeek-V4-Flash-180B` K160;
- revision: `7c360e1cd4a5168099dbc54d16d929bf6df04990`;
- vLLM: `4a6fd874725312c53883b1d53970af1d0eccfc3f`;
- XPU kernels: `d15ce87d07376be53ea2d6f7ae0262ab79f7cb7b`;
- oneCCL: `48fda4f0e074db005596d6899d5227d3f0316c12`;
- mode: TP4+EP, one active generation, FP8 KV, MTP1, reusable PIECEWISE
  graphs;
- new record flag: `VLLM_XPU_V4_M2_ROUTER_NORM=1`.

## Next implication

The M=2 router boundary is complete. Do not spend another server load tuning
its geometry unless a new shape appears. The next architectural lane should
attribute the remaining 6.58 ms/cycle dense-GEMM bucket by exact projection
shape and consumer, then test only a fusion or scheduling change with a
measured whole-cycle ceiling of at least 0.50 ms.
