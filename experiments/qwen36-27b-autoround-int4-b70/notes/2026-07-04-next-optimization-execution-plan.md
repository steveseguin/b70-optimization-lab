# 2026-07-04 - Qwen27 next optimization execution plan

## Objective

Beat the current valid Qwen27 one-B70 record without lowering quality or using
cache/history effects:

- model: `webhie/Qwen3.6-27B-int4-AutoRound`;
- current mode: AutoRound INT4 W4A16 + runtime INT8 LM-head with BF16 scales;
- current strict fresh record: `65.27648650325429 tok/s` median generated-token
  throughput for tokens 1-100 after TTFT;
- LocalMaxxing: already approved as `cmr5iu3gk00bfq901nidgcana`;
- quality: repeat32 and 1K needle passed, `baseline_match_all=true`;
- validity: fixed realistic Qwen suite, each prompt once, `cached_tokens=0`,
  no prompt/KV/context/response reuse, no n-gram/history acceleration,
  target-verified `qwen3_next_mtp`.

This plan supersedes further config roulette. The next credible speed lane is
source/kernel work around full LM-head/logits materialization.

## Progress update - 2026-07-04

Phase 0 and Phase 1 are complete and captured in
`2026-07-04-phase0-phase1-baseline-and-timing.md`.

- Phase 0 reproduced the current record family at `65.56930784255283 tok/s`
  median for generated tokens 1-100 after TTFT, with `cached_tokens=0` on all
  prompts.
- Phase 1 refreshed timing on the same BF16-scale INT8-LM-head recipe. The
  timing run is diagnostic only because sync instrumentation perturbs
  throughput, but it confirmed the main waste: `2258` LM-head/logits calls over
  `540` verifier steps (`~4.18` calls/step), with
  `lm_head_int8.gemm_w8a8` alone costing about `10.61 ms` per verifier step.
- The current next step is Phase 2: either build a real native tiled/XMX
  LM-head top-1/candidate-max prototype, or first add a narrow accepted-token /
  logits-call diagnostic if the native kernel path needs better acceptance
  context.
- A cheap Phase 2 precheck tested the existing Xe2 grouped W8A8 kernel as a
  single-expert dense LM-head backend. It is closed as a no-win:
  `2026-07-04-lmhead-backend-microbench-no-win.md`. oneDNN remains faster for
  rows `1-4`, and grouped W8A8 rejects BF16 weight scales.
- The compact native `int8_lm_head_top1_w8a8` full-vocab top-1 kernel was
  also closed as a no-win:
  `2026-07-04-compact-lmhead-top1-kernel-no-win.md`. It was exact, but the
  best 8x64 policy measured `2.66-2.68 ms` versus dense oneDNN + argmax
  `2.57-2.61 ms` for rows `1-4`.
- The semantic candidate-max version is now closed too:
  `2026-07-04-lmhead-candidate-max-kernel-no-win.md`. It returned true top
  IDs/values plus per-row candidate scores exactly, but measured only `1.01x`
  at rows `1` and regressed rows `2-4` (`0.98x`, `0.97x`, `0.96x`). Do not
  wire this op into vLLM.
- Acceptance tracing and scheduler-only adaptive MTP depth are now closed:
  `2026-07-04-spec-acceptance-and-adaptive-depth-no-win.md`. Fixed MTP3 emits
  about `2.70` tokens/verifier step; adaptive truncation passed strict
  validity but lost (`45.75`, `61.51`, `60.91 tok/s`) because it reduced
  emitted tokens/step and increased verifier steps. Do not resume
  scheduler-only adaptive depth unless proposer generation and verifier rows
  are both made dynamically depth-aware.
- True shorter proposer groups remain blocked:
  `2026-07-04-dynamic-depth-placeholder-reject-retry-no-win.md`. Retrying the
  dynamic drafter-depth prototype with upstream-style placeholder `-1` rejection
  still crashed the second strict-suite request with the same XPU
  `Indexing.h:622` assert. Partial groups are not a sampler-only fix; they need
  explicit support across proposer output, verifier metadata, sampler rows, GDN
  state commit, and graph capture shapes.
- The current recipe's shallow-depth gap is now closed too:
  `2026-07-04-webhie-mtp1-mtp2-depth-coverage-no-win.md`. MTP1/cg8 reached
  `51.246`, MTP2/cg8 `59.589`, MTP3/cg8 control `64.730`, and MTP4/cg8
  `59.886`, all strict/fresh with `cached_tokens=0`. MTP3/cg8 remains the
  policy.
- The current webhie/BF16-scale capture-size question is now closed:
  `2026-07-04-webhie-bf16scale-capture-size-screen-no-win.md`. A strict
  same-window four-GPU pass found cg8 remains best on the active recipe:
  cg4 `64.507`, cg8 control `65.153`, cg16 `63.500`, cg32 `64.071`, all with
  `cached_tokens=0`. Do not repeat capture-size sweeps for this exact recipe
  unless a source change alters graph shapes, row counts, or acceptance.
- The INT8 oneDNN GEMM scratchpad ring-size question is closed no-promo:
  `2026-07-04-int8-gemm-scratchpad-ring-screen-no-win.md`. Ring4 produced
  high support rows (`65.708`, `65.817`), but paired crossover deltas against
  ring1 controls were only `+0.42%` and `+0.27%`, so the movement is variance,
  not a new recipe.
- EAGLE v2 is also closed after one bounded stronger-draft screen:
  `2026-07-04-eagle-v2-stronger-offline-screen-no-endpoint.md`. A four-GPU
  offline diagnostic tested larger one-layer drafts and a residual two-layer
  variant. Best heldout mean accepted was only `0.6953125`, and all-96 training
  to separate calibration was only `0.44091796875`, so there is no endpoint
  candidate and no LocalMaxxing result. Do not reopen EAGLE endpoint sweeps
  without a materially better data/training/init idea.
- Draft top-k calibration is now measured and bounded:
  `2026-07-04-draft-topk-calibration-diagnostic.md`. The target verifier token
  is inside the built-in draft top-32 for `96-99%` of positions, and an
  impossible oracle reranker would raise the diagnostic run from `2.712` to
  `3.910` target-verified tokens/step. A larger 96-prompt non-final trace
  confirmed base `2.595` vs oracle `3.864`, but prompt-heldout margin reranking
  was flat and sparse token-bias reranking regressed. A small learned top-k MLP
  trained on the 96-prompt trace and evaluated on the separate 24-prompt trace
  improved only `2.7123 -> 2.7184` target tokens/step, too little to justify
  runtime overhead. Do not ship a heuristic or small top-k reranker. Future
  accepted-token work needs a materially stronger reranker/drafter or
  architecture on isolated non-final data, then held-out evaluation before
  endpoint testing.
- Draft top-k64 confirms the same limit:
  `2026-07-04-draft-topk64-and-sequential-reranker-limit.md`. A 96-prompt
  fresh/cached-zero diagnostic trace found target-in-top64 rates of
  `99.7%`, `98.4%`, and `96.8%` by draft position, but held-out margin
  reranking stayed flat (`2.626226` target tokens/step) and sparse token-bias
  reranking regressed (`2.621322`). The independent top-k64 oracle
  (`3.924200` heldout target tokens/step) is not directly implementable for
  sequential MTP because changing earlier draft tokens invalidates later draft
  rows; the final-slot upper bound (`2.787207`) still requires recomputing or
  branching the target bonus row and is below the threshold worth endpoint
  work. Do not reopen cheap post-hoc top-k reranker patches.

## Current waste estimate

The best available timing for this record family shows the MTP3 path still
spends most avoidable time in LM-head/logits:

| Bucket | Estimate per MTP step | Notes |
| --- | ---: | --- |
| dense LM-head / full logits | ~`10.7 ms` | draft ~`8.0 ms`, target verifier ~`2.7 ms`; cleanest waste because greedy/spec needs top IDs and selected scores, not full `[rows, vocab]` logits |
| target verifier forward / core model pass | ~`24-28 ms` | largest bucket, but mostly required target compute |
| MTP proposer model forward | ~`2.1 ms` | not the main issue |
| sampler / rejection / argmax / bookkeeping | ~`0.5-1.0 ms` | prior sampler plumbing was no-win |
| state copies / metadata / buffer copies | ~`<0.1-0.3 ms` | not worth chasing unless a fresh trace shows a hot path |

Current strict decode is about `15.3 ms/generated-token`. With MTP3, that
implies roughly `2.6 generated tokens/verifier step` and about `40 ms/step`.

Likely upside:

1. A standalone full-vocab native top-1 / candidate-max kernel has now failed
   twice. Future LM-head work needs a genuinely better primitive: oneDNN/XPU
   integrated top-ID/candidate-score epilogue, fewer LM-head calls/rows before
   GEMM, or a single-launch reduction design that beats dense oneDNN. Do not
   repeat another wrapper around the same full-vocab scan plus second reduction.
2. Draft-side LM-head calls are the larger avoidable bucket, but sequential
   MTP3 cannot simply batch them: each next draft hidden state depends on the
   previously sampled draft token. The dedicated audit is
   `2026-07-04-draft-lmhead-batching-and-dflash-next-blocker.md`. Avoid
   repeating draft row-batching or local-argmax wrappers unless the producer
   changes materially.
3. Improving accepted tokens/step toward `3.3-4.0` without increasing step cost
   is the route toward `90-100 tok/s`, but the top-k64 diagnostic shows this
   likely requires a real stronger drafter/branching design rather than
   post-hoc reranking.
4. DFlash/parallel drafting is the architectural way to remove sequential draft
   generation, but mixed full/sliding support needs multi-KV-group drafter
   metadata and per-group future-query block tables. Do not delete the
   single-KV assertion as a shortcut.
5. TTFT/prompt work is valuable separately: median TTFT is about `604 ms`, so
   wall-clock full128 is only about `49 tok/s` even though after-TTFT decode is
   about `64-65 tok/s`.

## Lessons that must constrain the plan

Do not repeat these as-is:

- naive scalar full-vocab fused top-1: correct in smoke, but about **1000x**
  slower (`2704.287 ms` vs `2.690 ms`);
- Python/chunked oneDNN top-1: no-win;
- output-buffer reuse: no-win;
- exact target argmax-only sampler plumbing: no-win because `get_top_tokens()`
  still materializes full logits;
- draft local-argmax plumbing: flat/no-win;
- bonus-token argmax fast-path: same-window no-win;
- draft-only row-count shortcut: invalid/collapsed;
- FP16 INT8-LM-head scale storage: no-win (`62.902 tok/s`);
- webhie target-only BF16-scale scope: lower TTFT but failed repeat32 once.

Useful historical analogy:

- Gemma improved heavily when verifier work avoided unnecessary full-output /
  sampled-id work, but only when semantics stayed target-verified and quality
  gates remained strict. Qwen must follow the same discipline: exact target
  replacement, exact target-owned bonus behavior, and no history/cached
  acceleration.

Local references to review before coding:

- `../../../docs/model-optimization-guide.md` - start-to-finish model
  optimization workflow for future agents;
- `../../../docs/research-workflow-playbook.md` - variance handling, four-GPU
  screens, no-cheating promotion gates, and reusable prompts;
- `../../../results/qwen36-27b-autoround-int4-b70/HANDOFF.md` - current Qwen27
  record identity, closed lanes, and active patch stack pointers;
- `../../../results/qwen36-27b-autoround-int4-b70/README.md` - promoted result
  packets and interpretation of LM-head / verifier bottlenecks;
- `../../../results/gemma4-26b-a4b-q8-b70/optimization-focus-map-20260628.md`
  and `../../../results/gemma4-26b-a4b-q8-b70/HANDOFF.md` - the Gemma verifier
  optimizations that inform the Qwen LM-head/verifier direction.

## Phase 0 - baseline lock

Reproduce the current record recipe before changing source:

- webhie checkpoint revision `f5750c90b3776db658594df5fe8051098226dd8e`;
- `VLLM_XPU_LM_HEAD_INT8=1`;
- `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16`;
- MTP3/cg8, `MAX_MODEL_LEN=2048`, `MAX_NUM_BATCHED_TOKENS=1024`;
- `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1`;
- `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`;
- strict realistic suite with token IDs and `cached_tokens=0`.

Record:

- GPU ID, driver/runtime, clocks/temperature if available;
- exact git heads and patch snapshot;
- env vars and launcher command;
- strict result JSON and server log path.

Completion:

- current recipe reproduces within expected variance, or the variance/regression
  cause is documented before testing new changes.

## Phase 1 - fresh timing table

Run a current timing diagnostic on the exact BF16-scale webhie recipe. The older
timing is good enough to choose a direction, but the next kernel lane deserves a
fresh table.

Measure:

- draft LM-head/logits;
- target LM-head/logits;
- proposer forward;
- target verifier/model forward;
- rejection sampler;
- GDN/state/bookkeeping;
- TTFT/prefill;
- accepted tokens/step and generated tokens/step.

Completion:

- a dated timing artifact exists with ms/step, tokens/step, and ms/generated
  token for the exact current recipe.

## Phase 2 - native fused LM-head prototype

Status: the first two standalone full-vocab implementations are closed no-win:
compact top-1 and candidate-max. Leave the requirements below as the semantic
gate for any future kernel, but the next attempt must use a materially different
primitive than the previous two-launch full-vocab reduction design.

Build a standalone native XPU prototype first. Do **not** wire into vLLM until
the microbench beats the current dense-logits path.

Target shape:

- rows `1-4`;
- hidden `5120`;
- vocab `248320`;
- INT8 LM-head weight copy with BF16 per-output-channel scales;
- BF16 hidden input and existing per-token INT8 activation quantization, unless
  quantization is also fused.

Required exact outputs:

- `top_token_ids` for each verifier/draft row;
- `top_values` for each row;
- draft candidate token values for each candidate row, if used for diagnostics
  or candidate-vs-max proof;
- target-owned bonus top ID/value for the bonus row;
- enough metadata to preserve exact target replacement on first mismatch.

Important correction to the earlier rough plan: **top-1 alone is not enough**
unless the integration still has all target replacement/bonus information.
For greedy verification, the kernel must provide the true target argmax token
for every verifier row whose draft token is not accepted, plus the true target
argmax for the bonus row on full accept. Candidate scores are useful, but the
global max ID/value is the semantic requirement.

Hard rejects:

- scalar per-vocab loops;
- Python/chunked oneDNN loops;
- anything slower than current
  `per_token_quant_int8_xpu + int8_gemm_w8a8 + dense logits + argmax`;
- any token mismatch against dense logits on randomized real-shape tests.

If native implementation is blocked:

- inspect current `vllm-xpu-kernels` oneDNN wrappers and sampler kernels first;
- then search current primary sources only: oneDNN docs/examples, Intel XPU
  kernel examples, vLLM/XPU code/issues, and relevant upstream PRs;
- record links, constraints, and why the blocker is real.

Completion:

- prototype is faster and exact on real shapes, or the kernel route is closed
  with a documented blocker and preserved patch/results.

## Phase 3 - vLLM integration

Gate integration behind a default-off env flag such as:

```text
VLLM_XPU_LM_HEAD_INT8_TOP1_CANDIDATE_MAX=1
```

Use it only when all semantics are safe:

- greedy/spec path only;
- no logprobs;
- no non-greedy sampling;
- no penalties or logits processors that can change argmax;
- no bad-word or allowed-token masks unless the kernel supports them exactly;
- no fallback ambiguity around padding / `org_vocab_size`;
- tie behavior must match current argmax closely enough for strict hash gates.

Fallback to dense logits for every unsupported case.

Completion:

- vLLM server starts with the flag;
- controlled probes produce identical token IDs to the dense path;
- unsupported request modes fall back safely.

## Phase 4 - validation and variance

Validation ladder:

1. microbench parity and speed;
2. short deterministic smoke;
3. strict fresh realistic suite;
4. repeat32 quality and 1K needle;
5. same-window A/B or crossover if gain is near variance.

Promotion gate:

- fixed Qwen realistic prompt suite;
- each prompt once as a cold response;
- `cached_tokens=0` every row;
- no prompt/KV/context/response reuse;
- no n-gram/history acceleration;
- target model and runtime quantization identity clearly labeled;
- target-verified speculative decoding only;
- primary metric: median generated-token throughput for tokens 1-100 after
  TTFT;
- also capture p10, mean, TTFT, wall-clock full output, full128/512 if used,
  prompt/output hashes, runtime commit, env vars, flags, logs.

Variance rule:

- if the gain is under about `2%`, use four B70s for same-window/crossover
  confirmation;
- if the gain is under about `1%`, treat it as inconclusive unless paired
  prompt-level analysis supports it;
- collect temperature/clocks when unexplained variance appears.

Completion:

- a valid record beats `65.27648650325429 tok/s`, quality passes, variance is
  handled, and the result is documented; or the candidate is recorded no-win /
  invalid with artifacts preserved.

## Phase 5 - accepted tokens per step

Only start this after the LM-head route is either promoted or closed.

Work:

- profile accepted tokens/step on the strict suite;
- identify prompt classes with under-acceptance;
- test acceptance-improving changes only if target verification remains exact;
- avoid n-gram/history/repeated-output acceleration for headline claims.

Completion:

- accepted tokens/step improves with strict quality and valid fresh throughput,
  or the lane is documented no-win.

## Phase 6 - prompt and TTFT service lane

Keep separate from the short decode record.

Build a prompt ladder:

- 128, 512, 2K, 4K, 8K, 16K, 24K/32K as feasible.

Record:

- TTFT;
- prefill tok/s;
- decode tok/s after TTFT;
- wall-clock full-output tok/s;
- VRAM;
- quality/needle result;
- `cached_tokens=0`.

Any prompt-speed change must rerun the short realistic decode suite to prove no
decode regression.

Completion:

- prompt/prefill win is documented separately with no short-decode regression,
  or the service lane is closed no-win.

## Completion definition for the overall plan

The plan is complete only when one of these end states is true:

1. **Record win:** a new strict fresh-response record beats
   `65.27648650325429 tok/s`, passes quality, has variance support when
   needed, is documented, committed, pushed, and submitted to LocalMaxxing.
2. **Kernel route closed:** the fused LM-head / candidate-max route is proven
   non-viable with current primitives or prototype performance, and the patch,
   benchmark, logs, and blocker analysis are preserved.
3. **Non-kernel lanes closed:** all remaining non-kernel follow-ups are recorded
   as no-win/invalid, no valuable artifacts are untracked, and the Qwen27 docs
   clearly state the current record and next credible blocker.

Do not call the plan complete based on a synthetic score, a repeated-prompt
speedup, a run with missing `cached_tokens=0`, a quality failure, or a result
inside variance without confirmation.

## Required artifact hygiene

For every meaningful attempt:

- save the patch or exact config diff;
- save the command/env/run identity;
- save strict result JSON, logs, and quality output where applicable;
- record whether the attempt is win/no-win/invalid/inconclusive;
- update the Qwen27 handoff if the current recommendation changes;
- commit and push focused artifacts;
- submit to LocalMaxxing only for a new valid record.

## Status update: 2026-07-04

Phase 2 was executed far enough to close the standalone compact full-vocab
top-1 kernel route as a no-win. The native
`torch.ops._xpu_C.int8_lm_head_top1_w8a8` prototype built, exported, and was
token-exact against dense `int8_gemm_w8a8(...)->argmax`, but the final 8x64
policy still measured slower than oneDNN dense plus argmax on the real Qwen27
LM-head shape: compact `2.66-2.68 ms` versus dense `2.57-2.61 ms` for rows
`1-4`. Evidence and patch are recorded in
`2026-07-04-compact-lmhead-top1-kernel-no-win.md`.

The plan should now continue with the non-standalone verifier lanes: reduce
LM-head call/row count per verifier step, improve accepted tokens per target
verifier step, or find a oneDNN-integrated top-1/top-k post-op that avoids a
second reduction launch.

## Status update: 2026-07-04 explorer synthesis

Two independent source/result audits agreed on the current frontier:

- `get_top_tokens()` is already the right semantic integration point, and the
  all-greedy rejection sampler can already consume precomputed target
  top-token IDs, but the producer still materializes dense logits through the
  INT8 LM-head path before reducing. Repeating sampler plumbing or local
  argmax flags is therefore no-win until the producer changes.
- Current Qwen3.6 27B public MTP variants still appear to use a single MTP
  layer (`mtp_num_hidden_layers=1`) recursively rather than a true
  multi-layer per-position drafter. This matches the local checkpoint audit and
  explains why MTP4/MTP5 lowers acceptance. Fresh external references checked:
  `https://huggingface.co/sakamakismile/Qwen3.6-27B-Text-NVFP4-MTP`,
  `https://huggingface.co/unsloth/Qwen3.6-27B-MTP-GGUF/discussions/2`,
  `https://huggingface.co/originalGeek/Qwen3.6-27B-unsloth-MTP-Q8_0-HEAD-ONLY`,
  and `https://huggingface.co/kradih/Qwen3.6-27B-MTP-4bit-MLX`.
- oneDNN public docs still describe dense MatMul output plus supported
  post-op/fusion patterns, not an exposed MatMul primitive that directly emits
  argmax/top-k/candidate-reduced values for this LM-head use case. Fresh refs:
  `https://uxlfoundation.github.io/oneDNN/dev_guide_matmul.html` and
  `https://uxlfoundation.github.io/oneDNN/dev_guide_graph_matmul_fusion_patterns.html`.
- Partial speculative groups are not a small scheduler tweak on this XPU/GDN
  stack. The scheduler has an explicit
  `VLLM_XPU_SPEC_DECODE_DISABLE_PARTIAL_DRAFT_GROUPS` escape hatch, and the
  previous dynamic-drafter prototype crashed as soon as it created a shorter
  group. The upstream-style placeholder `-1` rejection retry failed the same
  way, so a real fix must update scheduler, `SpecDecodeMetadata`, graph capture
  assumptions, sampler row handling, and GDN/Mamba state postprocess together.

Target-only lazy-verifier arithmetic correction:

- Full note:
  `2026-07-04-lmhead-upper-bound-and-priority-correction.md`.
- Recorded timing: `2258` LM-head calls over `540` verifier steps, with
  `lm_head_int8.gemm_w8a8` at about `10.61 ms/step`.
- Estimated draft LM-head cost: `~7.91 ms/step`; target verifier LM-head cost:
  `~2.54 ms/step`.
- With the recorded per-position acceptance (`0.784`, `0.559`, `0.381`), a
  perfect conditional target verifier would need `1 + p0 + p1 + p2 = 2.724`
  target rows instead of `4`.
- Even if row cost scaled linearly inside a native op, target-only lazy
  verification saves only about `0.81 ms/step`, estimating
  `65.28 -> ~66.58 tok/s`. That is useful but too close to variance to be the
  first expensive implementation lane.

Corrected ranked next implementation lanes:

1. **oneDNN/XPU-integrated top-ID producer for all greedy LM-head calls**:
   replace dense-logit production behind `get_top_tokens()` with a primitive
   that preserves oneDNN-class GEMM efficiency while returning exact top
   IDs/values. This must help both the three serial draft greedy calls
   (`~7.9 ms/step`) and the target verifier call (`~2.5 ms/step`). This is the
   only direct LM-head route with enough theoretical upside to matter, but it is
   high-risk kernel work because the standalone full-vocab top-1 op already
   lost.
2. **Target-matched drafter training/calibration**: improve accepted tokens per
   verifier step on held-out realistic-style data, with exact target
   verification and no final-suite leakage. This attacks the other large lever:
   moving emitted tokens/step toward `3.3-4.0` without increasing step cost.
   Draft top-k tracing shows the target is usually present in the built-in
   draft top-32, but simple token-bias/margin reranking is flat or worse on
   prompt-heldout splits, and a small learned top-k MLP barely moved cross-suite
   target tokens/step (`+0.006`). The next attempt needs a materially stronger
   learned drafter/reranker or stronger architectural draft path, not a static
   heuristic or tiny top-k scorer.
3. **Native lazy greedy target verifier op**: still valid as a later cleanup
   once a better top-ID producer exists, or if it can be fused with the
   producer, but target-only row skipping is not enough by itself.
4. **True partial-group support for dynamic drafter depth**: only worth doing
   if the goal is deeper metadata/graph engineering. Do not retry the old
   Python/scheduler-only adaptive-depth patches; they either paid full proposer
   cost or crashed partial groups.

Immediate rule: do not launch more endpoint benchmarks until the candidate is
one of the ranked mechanisms above. The current repo has enough evidence that
configuration roulette around MTP depth, parser mode, capture size, MBT, scale
dtype, target-only scope, and sampler plumbing is exhausted.
