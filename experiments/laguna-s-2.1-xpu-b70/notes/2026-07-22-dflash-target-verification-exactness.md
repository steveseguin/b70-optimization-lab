# Laguna S 2.1 DFlash target-verification exactness — 2026-07-22

## Result first

- Exactness: **7/7 prompts matched token-for-token**, comprising all six cold
  realistic-suite prompts at 128 output tokens plus a 511-token cold rollover
  prompt crossing the 512-token SWA boundary (19 output tokens).
- Exact DFlash median: **7.448971812987762 tok/s** for generated tokens 1–100
  after TTFT; p10 4.295573168638381, mean 7.280232291299225.
- Acceptance: **542/1736 = 31.22119815668203%**, over 248 draft cycles;
  mean accepted draft tokens/cycle 2.185483870967742 and observed emitted
  tokens/cycle 787/248 = 3.1733870967741935.
- The earlier **48.980858 tok/s** result remains diagnostic and inexact. The
  conservative exactness implementation deliberately serializes target rows,
  so it is not a speed promotion.
- No LocalMaxxing submission was made.

## Root cause

The first reported output mismatch was generated-token index 1: the target-only
q=1 PIECEWISE run chose token 604 while q=8 PIECEWISE verification chose 395.
The suspected DFlash full-attention override was not the cause. The final
rollover gate matches across the 512-token SWA boundary.

The component cross isolated multiple shape-dependent numerical paths:

1. q=1 XPU FlashAttention dispatches to paged decode, while q=8 verifier
   dispatches to chunk prefill. At target layer 0, attention input, QKV, Q/K
   norm, RoPE and V were bitwise equal; the first mismatch was the attention
   kernel output: 129/1536 BF16 values, max absolute delta 0.00048828125.
2. Re-expressing q=8 as eight q=1 pseudo-sequences made attention bitwise equal.
   The next mismatch was target layer-0 `o_proj`: 897/3072 values, max delta
   0.0009765625. The INT4 GEMM and XCCL reduction both choose M/message-size
   dependent paths.
3. Rowwise M=1 projection and reduction moved the first mismatch to layer-1
   sparse MoE output: 903/3072 values, max delta 0.000244140625.
4. A second prerequisite was exposed: the unpatched target-only q=1 teacher was
   itself non-repeatable. Identical cold requests in one server changed token 0
   or later greedy tokens. A same-prompt component trace first found drift at
   layer-3 `o_proj` (945 elements, max 0.000244140625); after rank-ordered TP
   reduction, the first remaining drift was layer-21 attention gating
   (119/283392 elements, max 0.00048828125) from the batched M=123 INT4 gate
   projection. The M>1 MoE remap also uses atomic row counting.

The precise cause is therefore not SWA metadata: it is the combination of
q-width-dependent attention dispatch, M-dependent INT4 GEMMs, unordered XCCL
reduction trees, and atomic M>1 sparse-MoE remap/gather. Laguna's narrow logit
margins amplify one-ULP BF16 differences into different greedy tokens.

## Fix

vLLM commit `d26fe57b3` adds an opt-in exact target path under
`VLLM_XPU_EXACT_SPEC_ATTN=1`:

- represent a one-sequence q=2..8 verifier chunk as q one-token pseudo-sequences
  in one paged-decode attention launch, with repeated block tables and growing
  sequence lengths;
- run target QKV, attention gate/output, dense projections, sparse MoE, and
  vocabulary head as M=1 rows for real prompt/verifier widths up to 512;
- replace target TP/EP all-reduce with all-gather plus BF16 additions in fixed
  rank 0,1,2,3 order;
- keep DFlash model layers out of the target-only row-serialization tags;
- retain environment-gated component tensor tracing for future diagnosis.

The q=1 reference uses the same deterministic target path. Two identical
123-token cold prefills were bitwise equal through all 48 traced layers after
the final fix.

## Exactness and throughput evidence

Target-only deterministic q=1:

- packet: `/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/exactness-q1-final-eager-bf16-20260722/bench.json`
- median: 12.560152959605336 tok/s;
- rollover: `/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/exactness-q1-final-eager-bf16-20260722/rollover-511.json`.

Exact DFlash:

- packet: `/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/exactness-dflash-final-eager-bf16-20260722/bench.json`
- median: 7.448971812987762 tok/s;
- p10 / mean: 4.295573168638381 / 7.280232291299225 tok/s;
- full-response median: 7.613067648304684 tok/s;
- median TTFT: 5465.005746053066 ms (cold prefill is also row-serialized);
- rollover: `/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/exactness-dflash-final-eager-bf16-20260722/rollover-511.json`.

All six realistic output hashes and complete token arrays match between q=1
and DFlash. Both packets report `cached_tokens=0` for every suite row.

## Exact decode-cycle profile

Profile summary:
`/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/exact-dflash-cycle-profile-20260722/summary.json`.
Four retained decode cycles on four ranks were used. The normal-run counters
give approximately 426.0 ms/cycle (3.1734 observed emitted tokens/cycle divided
by 7.449 tok/s). oneCCL device timestamps are distorted on this stack, so the
collective row uses inclusive CPU API spans; noncollective rows use XPU kernel
durations.

| Stage | ms/cycle | Share | Evidence |
|---|---:|---:|---|
| Attention | 0.425 | 0.1% | 96 attention kernel launches/cycle |
| MoE routing/remap/gather/scatter | 6.382 | 1.5% | 1504 launches/cycle |
| Expert INT4 GEMMs | 22.826 | 5.4% | 752 launches/cycle |
| Rank-ordered collectives | 150.9 | 35.4% | 777 collective calls/cycle; inclusive API spans |
| Dense/QKV/vocab GEMMs | 19.613 | 4.6% | 2688 GEMM launches/cycle |
| Other device kernels | 10.7 | 2.5% | norms, activation, cache update, copies |
| Host/Python launch and synchronization residual | 215.2 | 50.5% | normal cycle minus the measured stages |

The profiler itself inflated host cycles to 1.6–3.0 seconds; those profiled
request times are not used as throughput evidence.

## Next optimization targets

1. **Batched deterministic q=8 target verification and fused rank-order
   collectives.** This should remove most of the 777 collectives and Python
   row loops, recovering roughly 300–350 ms/cycle. Returning to the old
   diagnostic 90.15 ms/cycle would yield about 35.3 tok/s at the current exact
   acceptance, or about 49 tok/s if the old 4.416 emitted/cycle is restored.
2. **Fixed-M8, top-10, EP4 direct MoE.** Fuse RowsPerExpertCount, remap, gather,
   the two expert GEMMs and the deterministic rank combine. Routing plus expert
   compute is 29.2 ms/cycle today; a 10–15 ms recovery after target batching is
   worth roughly another 7–10 tok/s near the 75–90 ms/cycle regime.

## Commits and safety

- vLLM: `d26fe57b3` on
  `experiment/laguna-s-2.1-xpu-bringup-20260721`.
- XPU kernels: unchanged at
  `c615c38fb79d4035118c05675565dbf7e2443a90` on
  `experiment/laguna-s-2.1-fwht-20260721`.
- DeepSeek preserve tags and branches were not modified.
- All model/cache/run writes stayed under the Corsair artifact root; no
  `/mnt/fast-ai` writes and no DeepSeek held-out packs were used.

