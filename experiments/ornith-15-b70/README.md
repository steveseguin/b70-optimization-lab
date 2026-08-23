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
- **MoE shared-branch residual/RMSNorm — ACCEPTED +1.41% incremental
  serving:** the exact Qwen-derived `routed + shared -> ffn_out`, then
  `ffn_out + residual -> l_out -> RMSNorm -> weight` boundary appears in all
  40 MoE layers. The extended fusion preserves both rounded FP32 ADD outputs
  in their graph buffers before the unchanged RMS reduction. Mirrored engine
  means improved `120.260 -> 121.456 tok/s` (+0.99%); fresh-server means
  improved `116.406 -> 118.048 tok/s` (+1.41%), with every candidate above
  every control. Forced output was byte-identical and all canaries passed. The
  complete eight-feature stack removes 600 launches/token. See
  `notes/2026-08-23-ornith35b-moe-shared-residual-rms-positive.md`.
- **GDN RMSNorm/SiLU gate — ACCEPTED +0.78% incremental serving:** the
  Qwen3.5-derived recurrent boundary combines the existing per-head RMS/weight
  and SiLU/gate kernels while preserving the rounded FP32 normalization value.
  Mirrored engine means improved `121.287 -> 121.698 tok/s` (+0.34%);
  fresh-server means improved `116.535 -> 117.446 tok/s` (+0.78%). The
  complete nine-feature stack removes 630 launches/token. See
  `notes/2026-08-23-ornith35b-gdn-rms-silu-gate-positive.md`.
- **In-place GDN state I/O — ACCEPTED +6.80% incremental serving:** this
  transfer from our Qwen work removes the remaining recurrent state
  `GET_ROWS` by reading and writing the sole persistent state row in place.
  Exact shape, identity, ownership, non-overlap, and consumer gates fail
  closed. Mirrored engine means improved `122.074 -> 129.870 tok/s` (+6.39%);
  fresh-server means improved `118.148 -> 126.179 tok/s` (+6.80%). Every
  candidate exceeded every control, forced 128-token output was byte-identical,
  exactly 3,810 hits were recorded, and objective canaries passed. The
  complete ten-feature stack removes 660 launches/token. See
  `notes/2026-08-23-ornith35b-gdn-state-io-positive.md`.
- **Full-attention Q/K RMSNorm-IMRoPE — ACCEPTED +1.87% incremental
  serving:** following Ornith's Qwen lineage, the exact one-token
  normalization/scale/IMRoPE chain is fused in all 10 full-attention layers,
  with K written directly to the F16 cache. Mirrored engine means improved
  `130.397 -> 133.424 tok/s` (+2.32%); fresh-server means improved
  `126.470 -> 128.832 tok/s` (+1.87%). Every candidate exceeded every
  control, forced 128-token output was byte-identical, exactly 1,270 hits were
  recorded, and all objective canaries passed. The complete eleven-feature
  stack removes 700 launches/token. See
  `notes/2026-08-23-ornith35b-qk-norm-rope-positive.md`.
- **Level Zero copy-offload setting — ACCEPTED +1.09% incremental serving:**
  screening another setting from this lab's Qwen B70 work found that
  `UR_L0_V2_FORCE_DISABLE_COPY_OFFLOAD=1` transfers to Ornith, while the
  separately tested immediate-command-list setting does not. On the unchanged
  eleven-feature source stack, mirrored engine means improved
  `131.535 -> 133.188 tok/s` (+1.26%) and fresh-server means improved
  `128.166 -> 129.568 tok/s` (+1.09%). The candidate won 9/12 prompt-matched
  averages, forced output was byte-identical, and all freshness/finality gates
  passed. This is recipe-only and is not promoted globally. See
  `notes/2026-08-23-ornith35b-copy-offload-positive.md`.
- **Unified Runtime single-thread mode — CLOSED SERVING NEGATIVE:** layered on
  the accepted copy-offload setting, `UR_L0_SINGLE_THREAD_MODE=1` was
  byte-exact and improved mirrored raw-engine means by 0.31%, but fresh-server
  means regressed 0.11%. Prompt-matched means regressed 0.46% and the candidate
  won only 3/12 prompts. Keep it unset. See
  `notes/2026-08-23-ornith35b-ur-single-thread-serving-negative.md`.
- **Legacy copy-engine disable — CLOSED ENGINE NEGATIVE:** adding
  `UR_L0_USE_COPY_ENGINE=0` on top of the accepted V2 copy-offload setting was
  byte-exact but regressed mirrored engine means by 0.54%. It did not earn a
  server test and remains unset. See
  `notes/2026-08-23-ornith35b-ur-old-copy-engine-negative.md`.
- **GDN output-projection Q8 fusion — CLOSED CORRECTNESS NEGATIVE:** the
  Qwen-derived candidate tried to emit reordered Q8_1 directly from the
  accepted gated-normalization producer before each recurrent Q4_K output
  projection, which would remove 30 launches/token. Its poison matcher hit the
  intended node, but three increasingly conservative forms produced hashes
  different from the canonical transcript; even a global-barrier form followed
  by the stock quantizer failed with all 3,810 expected activations. No speed
  test was run, and the eleven-feature stack was restored. See
  `notes/2026-08-23-ornith35b-gdn-outproj-q8-correctness-negative.md`.
- **Optimized 0-32K context profile — PUBLISHED, MEASURED ONLY:** the exact
  eleven-feature package stack was swept at seven explicit depths with
  `pp2048`, `tg128`, five repetitions, flash attention on, F16 KV, and graphs
  off. Decode measured `138.978` tok/s at depth zero, `124.210` at 8K, and
  `96.996` at 32K; prefill measured `1397.348`, `1284.796`, and `1101.625`
  tok/s at those same depths. No point is interpolated or extrapolated. See
  `notes/2026-08-23-ornith35b-eleven-feature-depth-sweep.md` and the package guide.
- **Current-stack serialized profile — DIAGNOSTIC ONLY:** temporary device
  barriers ranked dense projections first and routed projections second after
  the eight accepted optimizations. These serialized values are never
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
- **Beta-sigmoid/GDN interaction on the nine-feature stack — CLOSED
  SERVER-NEUTRAL:** both the beta/GDN and downstream GDN RMS/gate fusions fired
  exactly and preserved the canonical transcript. Mirrored engine means rose
  `120.413 -> 121.933 tok/s` (+1.26%), but fresh-server means moved
  `117.630 -> 117.573 tok/s` (-0.05%). All freshness/final gates passed, so the
  engine-only gain is rejected. See
  `notes/2026-08-23-ornith35b-beta-gdn-nine-stack-server-neutral.md`.
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
- **Full-attention Q/K/V shared Q8 — CLOSED STRUCTURAL/CORRECTNESS NEGATIVE:**
  the ten Qwen-derived attention layers share an FP32 activation across Q, V,
  and K, but their one-token B70 path is reordered ESIMD DMMV, not Q8-MMVQ.
  A Q-only isolation already changed the deterministic transcript because the
  candidate changed algorithms; there are no incumbent Q8 launches to share.
  No throughput run was performed. See
  `notes/2026-08-23-ornith35b-attn-qkv-shared-q8-structural-correctness-negative.md`.
- **Four-row reordered ESIMD dense reuse — BROAD NEGATIVE / OUTPUT-HEAD
  NEUTRAL:** a Qwen-derived four-row activation-reuse candidate was byte-exact
  and hit the intended dense K-quant path, but regressed the broad Q2_K-Q6_K
  screen by 2.03%. Restricting it to the Q6_K output head produced only +0.087%
  in a mirrored engine screen. No server run was justified and the accepted
  stack is unchanged. See
  `notes/2026-08-23-ornith35b-dmmv-esimd-quad-negative-neutral.md`.
- **Four-row reuse at the large `2048→8192` projections — CLOSED NEGATIVE:**
  restricting the exact candidate to 30 recurrent QKV plus 10 full-attention Q
  calls removed the smaller shapes but still regressed a mirrored engine screen
  by 0.786%. The accepted pair kernel remains faster. See
  `notes/2026-08-23-ornith35b-dmmv-esimd-quad-large-negative.md`.
- **Direct FP32 router GEMV — CLOSED CORRECTNESS NEGATIVE:** the exact
  Qwen-derived `[256,2048] × [2048,1]` router boundary currently uses oneMKL
  GEMM. A narrow GEMV replacement hit all 5,080 intended calls but changed the
  forced deterministic transcript at byte 456. It was not timed or shipped.
  See `notes/2026-08-23-ornith35b-router-gemv-correctness-negative.md`.
- **Paired recurrent alpha/beta projection — CLOSED STRUCTURAL NEGATIVE:**
  both Q4_K `[2048,32]` projections share the same activation and otherwise
  satisfy the exact reordered-DMMV matcher, but llama.cpp intentionally assigns
  their non-overlapping outputs the same allocation. Computing them together
  would overwrite alpha before its consumers run. The alias guard rejected all
  pairs, no timing was performed, and the accepted stack is unchanged. See
  `notes/2026-08-23-ornith35b-alpha-beta-paired-buffer-alias-negative.md`.
- **Paired recurrent QKV/gate projection — CLOSED PERFORMANCE NEGATIVE:** the
  Qwen-derived projections safely have distinct overlapping outputs, and the
  mixed Q4_K/Q6_K candidate preserved exact dot arithmetic, matched the
  canonical transcript, hit all 3,810 calls, and removed 30 launches/token.
  Mirrored engine means nevertheless regressed `120.599 -> 119.585 tok/s`
  (-0.841%). It was not server-tested or shipped. See
  `notes/2026-08-23-ornith35b-qkv-gate-paired-performance-negative.md`.
- **Shared-expert scalar gate — CLOSED CORRECTNESS/PERFORMANCE NEGATIVE:** an
  aggressive one-kernel FP32 dot/sigmoid/broadcast form hit all 5,080 sites
  but changed deterministic output and was not timed. A conservative form kept
  the stock dot and fused only sigmoid+broadcast multiply; it was byte-exact,
  removed 40 launches/token, and improved the mirrored engine by 0.78%, but
  regressed valid fresh serving by 0.94% (`118.801 -> 117.686 tok/s`). Neither
  variant ships. See
  `notes/2026-08-23-ornith35b-shared-gate-fusions-negative.md`.
- **Routed-MoE row packing — CLOSED SERVER-NEUTRAL/SLIGHT-NEGATIVE:** a
  Qwen-transfer candidate packed two independent output-row subgroups into
  each routed gate/up and down workgroup without changing per-row arithmetic.
  It was byte-exact and improved mirrored engine means by 0.92%, but fresh
  serving moved `117.754 -> 117.559 tok/s` (-0.17%); both candidates lost to
  control A. Do not ship. See
  `notes/2026-08-23-ornith35b-moe-rowpack-server-neutral.md`.
- **Q6_K output-head workgroup occupancy — CLOSED ENGINE NEGATIVE:** reducing
  the exact `[248320,2048]` decode kernel from 32 independent row subgroups per
  workgroup to 16 or 8 preserved the canonical transcript but monotonically
  reduced engine rate (`121.576 -> 121.233 -> 121.087 tok/s`). No server test
  was justified. See
  `notes/2026-08-23-ornith35b-lmhead-subgroups-negative.md`.
- **Final output-head `GET_ROWS` bypass — CLOSED ENGINE NEUTRAL:** an execution
  audit first confirmed that accepted recurrent fusions already suppress every
  generic state gather in one-token decode; their serialized profile time was
  deferred-work attribution. A strict direct-FP32 bypass for the one remaining
  `result_norm` gather was byte-exact, hit all 127 generated tokens, and removed
  one launch/token, but mirrored engine means moved only
  `133.600 -> 133.655 tok/s` (+0.041%). No server test was justified. See
  `notes/2026-08-23-ornith35b-final-getrows-direct-neutral.md`.
- **No-model n-gram speculation — CLOSED NEGATIVE:** default `ngram-simple`
  accepted only 22/336 reported draft tokens and reduced the fresh-suite median
  from `113.000` to `96.424 tok/s` (-14.67%). A shorter N=4/M=8 profile failed
  to finalize its first HTTP response and was terminated. Keep the general
  recipe target-only. See
  `notes/2026-08-23-ornith35b-ngram-speculation-negative.md`.
- **Ornith 9B Q8 draft for 35B — CLOSED BEFORE FULL LOAD:** the measured draft
  is only 50.109 tok/s while the accepted target serves at 115.680 tok/s. Even
  perfect four-token acceptance with a free verifier is bounded at 62.64 tok/s,
  so the slow NFS load was stopped without claiming a run. See
  `notes/2026-08-23-ornith35b-ornith9b-draft-suitability.md`.
- **Embedded MTP verifier fusions — RESEARCH ONLY:** the model's Qwen-derived
  embedded predictor works, but MTP1 and MTP3 remain much slower than the
  then-accepted 117.446 tok/s target-only package (the later ten-feature target
  reaches 126.179). Extending residual/RMS fusions to 2-4
  verifier rows was exact and improved the mirrored MTP1 grand prompt mean by
  1.97%; extending the GDN RMS/gate fusion was exact but neutral. Both remain
  default-off research artifacts and do not enter the user recipe. This work
  also strengthens future validation: a realistic repeated-prompt canary is
  required in addition to short exact-answer canaries. See
  `notes/2026-08-23-ornith35b-embedded-mtp-verifier-fusions.md`.
- **Speculative decode:** investigate a substantially smaller and faster
  vocabulary-compatible draft separately. Label target-only and assisted
  results separately.

## Promotion gate

A candidate must have a reproducible matched A/B, exact runtime and model
identity, target-only versus assisted labeling, deterministic output evidence,
and two fresh-server serving measurements before it changes a public package.
