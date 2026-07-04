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

1. A real fused LM-head top-1 / candidate-max path could plausibly save
   `5-9 ms/step`, moving `65 tok/s` toward `75-85 tok/s` if quality holds.
2. Improving accepted tokens/step toward `3.3-4.0` without increasing step cost
   is the route toward `90-100 tok/s`.
3. TTFT/prompt work is valuable separately: median TTFT is about `604 ms`, so
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
