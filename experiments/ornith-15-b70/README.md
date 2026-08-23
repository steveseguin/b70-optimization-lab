# Ornith 1.5 decode optimization lab

This directory owns the lab's decode-focused optimization work for the
official Ornith 1.5 GGUF models. The maintained recipes remain in
`repro/ornith-15-*/`; outside reports are inputs to validation, not the source
of truth for a published recipe.

## In-scope models

- Ornith 1.5 9B dense, Q8_0, one B70.
- Ornith 1.5 35B-A3B MoE, Q4_K_M, one B70.

The inspected 35B GGUF has 41 layers, hidden width 2048, expert width 512,
256 routed experts, and 8 active experts per token. Its routed gate/up tensors
are Q4_K while routed down tensors are Q6_K. Optimization tests must cover both
real single-token `MUL_MAT_ID` shapes rather than a nearby Qwen proxy.

## Measured starting points

The fresh target-only intake diagnostic on the four-B70 measuring host (one
visible B70 per process) reported:

| Model | Decode median | p10 | Evidence |
| --- | ---: | ---: | --- |
| 9B Q8_0 | 50.109 tok/s | 50.061 | `../qwen38-27b-b70/data/2026-08-22-neural-download-firstwave-baselines.json` |
| 35B-A3B Q4_K_M | 105.782 tok/s | 105.284 | `../qwen38-27b-b70/data/2026-08-22-neural-download-firstwave-baselines.json` |

These are diagnostic serving medians, not a promise that a different host,
binary, driver, or benchmark protocol will reproduce them.

## Decode campaign rules

1. Compare a candidate with a matched control: same model identity, binary
   base, device visibility, context, KV types, prompt/decode sizes, repetitions,
   and host state.
2. Record raw repetitions and identities. Do not interpolate or extrapolate a
   context point that was not measured.
3. A throughput result is not promotable until deterministic token/logit checks
   and the model's canary battery pass.
4. Preserve negative and neutral candidates so they are not rediscovered.
5. Credit an outside contributor only for the concrete patch or idea that
   survives our matched validation. The integrated patch and user recipe live
   here.

## First candidates

- **Dense command-graph A/B — CLOSED NEUTRAL:** matched local-file runs measured
  50.149 tok/s graph-off versus 50.169 graph-on (+0.0388%). The earlier apparent
  2x was a slow-NFS mmap confound, documented in
  `notes/2026-08-22-decode-first-screen.md`.
- **MoE graph eligibility — CLOSED NEGATIVE:** the eligibility correction from
  llama.cpp PR 25089 was useful as a concrete test input, with credit to
  Captain-Tripps for that idea. Our maintained port added exact dispatch gates
  and fixed a first-capture dependency by running the persistent expert reorder
  eagerly. Both real Ornith Q4_K/Q6_K shapes passed CPU equivalence, but the
  full model fell from a `101.846 tok/s` graph-off control mean to
  `48.805 tok/s` graph-on (`-52.08%`). Preserve the patch as a negative; do not
  enable `GGML_SYCL_ENABLE_GRAPH=1` for this lane. Evidence is in
  `data/2026-08-22-ornith35b-moe-command-graph-screen.json`.
- **Ordered MoE add reduction — ACCEPTED +4.85% serving:** the real graph
  reduces eight weighted expert rows with seven serial FP32 `ADD` launches in
  each of 40 layers. The strict default-off lab patch preserves the weighted
  multiplication and performs those seven ordered additions in one kernel,
  removing 240 launches/token. Raw-engine means improved `103.048 -> 108.098`
  tok/s (+4.90%); two-fresh-server means improved `99.664 -> 104.499` tok/s
  (+4.85%). The forced 400-token door-off/on output was byte-identical and the
  candidate canary battery passed. See
  `notes/2026-08-22-ornith35b-moe-add-reduce-positive.md`.
- **Recurrent convolution + SiLU — ACCEPTED +2.10% incremental serving:** the
  exact one-token `SSM_CONV -> SILU` pairs in 30 recurrent layers collapse to
  one kernel while stock state handling and Q/K L2 remain unchanged. Engine
  means improved `107.467 -> 108.740 tok/s` (+1.18%); fresh-server means
  improved `103.012 -> 105.171 tok/s` (+2.10%). Forced 400-token output was
  byte-identical and all canaries passed. The wider direct-state candidate is
  archived as a correctness negative. See
  `notes/2026-08-22-ornith35b-conv-silu-positive.md`.
- **Launch-census follow-up — TWO CORRECTNESS NEGATIVES:** the backend already
  absorbs all 40 MoE router chains plus its norm, unary, GDN-cache, and
  matmul/GLU opportunities. Paired recurrent Q/K L2 and shared-expert-tail
  fusions both hit every intended layer but changed fixed-seed generation, even
  in their strictest stock-intermediate forms. No speed result was promoted.
  See `notes/2026-08-22-ornith35b-launch-census-and-fusion-negatives.md`.
- **Convolution/SiLU work-group sweep — CLOSED NEUTRAL:** WG64 initially looked
  slightly faster than the accepted WG256, but the mirrored seven-sample repeat
  measured `109.643` versus `109.991 tok/s` (**-0.32%**). WG128 and WG512 also
  produced no screen win. Keep WG256; no server run was justified. See
  `notes/2026-08-22-ornith35b-conv-workgroup-neutral.md`.
- **Weighted routed-expert reduction — CLOSED CORRECTNESS NEGATIVE:** absorbing
  the remaining expert-weight `MUL` into the ordered reduction would remove 40
  more launches/token and about 5 MiB/token of temporary traffic. The narrow
  candidate matched every intended layer, but a same-binary forced 128-token
  greedy run diverged despite volatile FP32 products. Keep the weighted
  multiplication graph-visible; no timing result was promoted. See
  `notes/2026-08-22-ornith35b-weighted-reduce-correctness-negative.md`.
- **Ordered-reduction work-group sweep — CLOSED NEUTRAL:** explicit WG64,
  WG128, WG256, and WG512 scheduling preserved exact output, but the best arm
  was only 0.29% above the accepted implicit-range kernel and remained within
  sample noise; WG64 regressed 1.10%. Keep implicit scheduling. See
  `notes/2026-08-22-ornith35b-moe-add-workgroup-neutral.md`.
- **Residual + RMSNorm fusion — ACCEPTED +1.37% incremental serving:** the
  Qwen-derived graph has 80 residual additions/token immediately before fused
  RMSNorm/weight kernels. The new path preserves each graph-visible volatile
  FP32 residual and the stock reduction order while removing those launches.
  Engine means improved `109.629 -> 111.826 tok/s` (+2.00%); fresh-server
  means improved `106.319 -> 107.776 tok/s` (+1.37%). Forced 128-token output
  was byte-identical and all canaries passed. See
  `notes/2026-08-22-ornith35b-residual-rms-positive.md`.
- **Recurrent concat + state update — ACCEPTED +2.74% incremental serving:**
  Ornith's Qwen-derived recurrent path materializes a `[4,8192]` FP32
  convolution input and then copies rows 1-3 into persistent state. The narrow
  fusion preserves both graph-visible destinations in one launch across all 30
  recurrent layers. Engine means improved `111.523 -> 115.457 tok/s`
  (+3.53%); fresh-server means improved `105.767 -> 108.662 tok/s` (+2.74%).
  Forced 128-token output was byte-identical and all canaries passed. See
  `notes/2026-08-22-ornith35b-concat-state-positive.md`.
- **Direct recurrent gather + concat/state — ACCEPTED +1.12% incremental
  serving:** the strict one-row Ornith path now materializes the original
  `GET_ROWS` output, full `[4,8192]` convolution input, and shifted persistent
  state in one channel-owned kernel. It leaves `SSM_CONV` separate and loads
  every old state value before the in-place update. Engine means improved
  `114.559 -> 116.818 tok/s` (+1.97%); fresh-server means improved
  `110.646 -> 111.883 tok/s` (+1.12%). Forced 128-token output was
  byte-identical before and after matcher hardening, and all canaries passed.
  See `notes/2026-08-22-ornith35b-concat-state-direct-positive.md`.
- **Recurrent alpha-gate — ACCEPTED +2.04% incremental serving:** the exact
  32-element FP32 `alpha + ssm_dt.bias -> softplus -> ssm_a` chain appears in
  all 30 recurrent layers. The strict fusion materializes the original rounded
  ADD output and requires exact adjacency, names, shapes, layout, source order,
  output flags, and sole-consumer proofs. Pooled engine means improved
  `116.657 -> 118.040 tok/s` (+1.18%); fresh-server means improved
  `112.030 -> 114.314 tok/s` (+2.04%). Both candidate servers beat both
  controls, forced 128-token output was byte-identical, and all canaries
  passed. The complete stack removes 440 launches/token. See
  `notes/2026-08-22-ornith35b-alpha-gate-positive.md`.
- **Routed-expert gate/up — ACCEPTED +2.33% incremental serving:** the tuned
  reordered-Q4_K `MUL_MAT_ID` kernel now computes gate and up together and
  writes SWIGLU directly for all 40 MoE layers. It preserves each dot-product
  reduction order while removing a duplicate input quantization, a second
  routed GEMV, and a GLU launch per layer (120 launches/token). Engine means
  improved `118.229 -> 120.695 tok/s` (+2.09%); fresh-server means improved
  `113.043 -> 115.680 tok/s` (+2.33%), with every candidate above every
  control. Forced output was byte-identical and all canaries passed. The
  complete stack removes 560 launches/token. See
  `notes/2026-08-23-ornith35b-moe-gate-up-positive.md`.
- **Current-stack serialized profile — DIAGNOSTIC ONLY:** temporary device
  barriers ranked dense projections first and routed projections second after
  the seven accepted optimizations. These serialized values are never
  extrapolated to tok/s. They selected routed down plus its
  weighting/ordered-reduction tail for the next exactness-first test. See
  `notes/2026-08-23-ornith35b-current-stack-op-profile.md`.
- **Routed-down weighted reduction reinvestigation — CLOSED CORRECTNESS
  NEGATIVE:** three variants ranged from a fully fused reordered-Q4_K kernel
  to the stock down projection plus a graph-visible weighted reduction. All
  fired 2,540 times but changed the forced deterministic output, including the
  most conservative global-intermediate form. No speed test was run and the
  accepted stack is unchanged. See
  `notes/2026-08-23-ornith35b-moe-down-weighted-reduce-correctness-negative.md`.
- **Beta-sigmoid/GDN fusion — CLOSED NEUTRAL:** folding the 32-element beta
  sigmoid into GDN removed 30 launches/token and preserved byte-exact
  generation. The engine loop improved 1.04%, but fresh-server means moved
  only `112.900 -> 113.342 tok/s` (+0.39%); both candidates lost to control A
  and beat control B. Ordering noise dominated the effect, so the fusion is
  archived and not shipped. See
  `notes/2026-08-23-ornith35b-beta-gdn-neutral.md`.
- **Attention-gate copy bypass — CLOSED NEUTRAL:** the Qwen-derived attention
  path's ten strided gate copies were bypassed inside the already-fused
  sigmoid/multiply kernel. Exact output and the expected 10 launches/token
  were confirmed. The engine mean improved 0.95%, but fresh-server means moved
  only `113.383 -> 113.792 tok/s` (+0.36%) and the arms crossed. The candidate
  is archived and not shipped. See
  `notes/2026-08-23-ornith35b-attn-gate-cont-neutral.md`.
- **Shared recurrent Q8 input — CLOSED CORRECTNESS NEGATIVE:** Ornith's four
  recurrent projections share one FP32 activation, suggesting a direct
  Qwen-derived transfer that could remove 90 Q8-quantization launches/token.
  Retaining one quantization changed deterministic output even in a QKV-only
  diagnostic routed through the complete stock MMVQ wrapper. The candidate was
  not timed or shipped. See
  `notes/2026-08-23-ornith35b-shared-q8-correctness-negative.md`.
- **Four-row reordered ESIMD dense reuse — BROAD NEGATIVE / OUTPUT-HEAD
  NEUTRAL:** a Qwen-derived four-row activation-reuse candidate was byte-exact
  and hit the intended dense K-quant path, but regressed the broad Q2_K-Q6_K
  screen by 2.03%. Restricting it to the Q6_K output head produced only +0.087%
  in a mirrored engine screen. No server run was justified and the accepted
  stack is unchanged. See
  `notes/2026-08-23-ornith35b-dmmv-esimd-quad-negative-neutral.md`.
- **Direct FP32 router GEMV — CLOSED CORRECTNESS NEGATIVE:** the exact
  Qwen-derived `[256,2048] × [2048,1]` router boundary currently uses oneMKL
  GEMM. A narrow GEMV replacement hit all 5,080 intended calls but changed the
  forced deterministic transcript at byte 456. It was not timed or shipped.
  See `notes/2026-08-23-ornith35b-router-gemv-correctness-negative.md`.
- **No-model n-gram speculation — CLOSED NEGATIVE:** default `ngram-simple`
  accepted only 22/336 reported draft tokens and reduced the fresh-suite median
  from `113.000` to `96.424 tok/s` (-14.67%). A shorter N=4/M=8 profile failed
  to finalize its first HTTP response and was terminated. Keep the general
  recipe target-only. See
  `notes/2026-08-23-ornith35b-ngram-speculation-negative.md`.
- **Speculative decode:** investigate separately if kernel/graph work cannot
  approach the requested 2x user-visible rate. Label target-only and assisted
  results separately.

## Promotion gate

A candidate must have a reproducible matched A/B, exact runtime and model
identity, target-only versus assisted labeling, deterministic output evidence,
and two fresh-server serving measurements before it changes a public package.
