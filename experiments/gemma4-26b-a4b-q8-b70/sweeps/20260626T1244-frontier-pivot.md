# Gemma 4 26B Q8 Frontier And Pivot Note

Date: 2026-06-26

This note records the current state after the recent Gemma 4 26B A4B Q8
single-B70 work and the decision to stop spending most cycles on small
single-flag Gemma sweeps.

## Current Valid Best

- Model: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf` target/verifier.
- Draft: `gemma-4-26B-A4B-it-Q4_0-MTP.gguf` assistant only.
- Best valid fresh-response headline:
  `103.2992004295621 tok/s` after TTFT on the first measured no-cache row,
  `cached_tokens=0`.
- Supporting repeated-request mean: `102.19335537277364 tok/s`.
- Validation: `1536/1536` chat canary.
- LocalMaxxing: `cmqsylo2l011nqr011yydjvne`.
- Evidence:
  `data/gemma4-q8-gpu0-selectedsoftmax-weightedsum-pmin0136-full-20260625T031510Z/summary.json`.

The target remains `>150 tok/s` fresh-response. Warmed/history n-gram rows above
`200 tok/s` are not valid fresh-response records because they depend on repeated
benchmark continuations.

## Recent Near-Misses

The latest micro-op screens were valid but below the promoted record:

- `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1`:
  `102.246850 tok/s`, `128/128` canary.
- `LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1` plus
  `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1`:
  `102.994096 tok/s`, `128/128` canary.
- `LLAMA_GEMMA4_MOE_TOP_K=1`:
  valid but below record.

These were useful confirmation runs, but they are not enough movement to justify
more blind micro-flag sweeps.

## What The Audits Found

### Target-to-draft `h_nextn` handoff

`LLAMA_MTP_DRAFT_DEVICE_H_HANDOFF` does not remove the target-to-draft host
`pending_h` seed path for the direct-unroll fast path:

- direct-unroll seeds draft input from host `pending_h` in
  `/home/steve/src/llama.cpp-gemma-record-stack/common/speculative.cpp`;
- the existing device handoff helper copies draft output to the next draft input
  inside the draft context only;
- a real target-to-draft helper would need to copy a row of target `t_h_nextn`
  into draft `t_inp_embd` and fall back safely when graph reuse is not present.

This is real cleanup work, but profile evidence makes it low priority:
`accept_copy_ms` was tiny compared with target verifier/model time.

### MoE selected-down fusion

The direct selected-down weighted-sum family has already been tested:

- direct selected-down weighted sum: `101.606 tok/s` smoke, then
  `99.434 tok/s` scale-aware guarded smoke;
- selected-softmax plus fused-down combo: `101.512 tok/s`;
- direct-F32 selected-down: `100.829 tok/s`;
- parallel-slot selected-down: `102.237 tok/s`;
- fused GEGLU-down: `92.186 tok/s`;
- matmul-epilogue selected-down: `102.329 tok/s`.

The only narrow untested member would be a new combined direct-F32 plus
parallel-slot kernel. That is not just an env flag combo in the current source:
the direct-F32 path returns before the parallel-slot path can fire. Implementing
it would require another kernel variant and is low-confidence because the rest
of this family lost.

### Verifier LM-head / argmax

The verifier output shortcut family has also been covered:

- sampler bypass / greedy argmax was around `91 tok/s`;
- Q6_K fused-output-argmax supportfix passed but was only `103.019 tok/s`;
- `LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX=1` on the selected-softmax /
  weighted-sum stack was about `90.428 tok/s`;
- earlier multi-row verifier argmax paths either crashed, were guarded neutral,
  or landed below record.

A candidate-vs-max verifier op could be a different larger design, but it is
not another quick flag run.

## Interpretation

The Gemma record stack is now verifier dominated. The useful recent profile
showed target `process_ubatch_ms` taking nearly all target time, while draft
decode was a small fraction. The currently available small flags mostly shave
draft or materialization edges and do not attack enough target MoE / LM-head
work to reach `>150 tok/s`.

The next Gemma work should be one of these larger designs, not more repeated
micro-sweeps:

1. Router materialization fusion for verifier-sized decode shapes, avoiding the
   full argsort/materialize selected-experts/selected-weights path. This is
   invasive because ggml ops are single-output while the graph currently expects
   IDs and weights as separate tensors.
2. A true graph-level multi-token assistant unroll or fresh-valid speculation
   engine that raises accepted tokens per target verifier step without using
   warmed history.
3. A verifier candidate-vs-max acceptance op that avoids full LM-head rows while
   preserving exact greedy acceptance semantics.
4. A real target-to-draft device `h_nextn` handoff only after a profile proves
   that host copy matters.

## Pivot Decision

Given the small recent movement on Gemma (`102-103 tok/s` valid screens versus
the `103.299 tok/s` record), the better immediate ROI is to move similar
boundary-fusion effort to another lane.

Cross-lane audit ranking:

1. MiniMax M2.7 INT4 AutoRound: best next bet. Current strict speed lane is
   `89.314195` output tok/s / `119.085594` total tok/s at p512/n1536. Next work
   should target hidden-state collective/epilogue fusion such as MoE-output
   allreduce plus epilogue, or attention `o_proj` allreduce plus residual/RMSNorm.
2. Qwen3.6 27B Q4_0 GGUF TP3: concrete but smaller. The root-residual ordering
   hazard needs instrumentation before benchmark work.
3. Gemma 4 12B service: useful service routing/profile work, less raw
   single-session kernel upside.

Qwen3.6 35B remains closed for now: best strict-valid 4x result was
`93.55 tok/s`, with no valid `>150 tok/s` path.

## Next Action

Stop launching Gemma 26B Q8 screens unless the candidate is a material new
design. The next active engineering task should be MiniMax M2.7 source work
around graph-boundary collective/epilogue fusion, gated by its strict quality
suite before benchmarking.
