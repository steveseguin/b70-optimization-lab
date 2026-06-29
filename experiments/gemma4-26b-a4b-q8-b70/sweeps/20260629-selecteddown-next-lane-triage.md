# 2026-06-29 Gemma 4 26B Q8 selected-down next-lane triage

Purpose: continue from the current valid fresh-response record without repeating
closed configuration or verifier experiments.

## Current Record To Preserve

- Result directory:
  `data/gemma4-q8-gpu1-selecteddown-bf16retest-control-full512-20260629T051323Z/`
- LocalMaxxing approval: `cmqyrpox4021dqk01co5o4fcw`
- Primary metric: `115.8466634928202 tok/s` median generated-token throughput
  for tokens 1-100 after TTFT.
- Gate: fixed realistic cold suite, each prompt once, `cached_tokens=0` for
  every request, no prompt/KV/context/response/n-gram/history reuse.
- Target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`.
- Draft: `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`; target verification preserves
  target-model output quality.
- Key env/flags:
  `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`,
  `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1`,
  `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`,
  `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`,
  `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_DIRECT_VDR2=1`,
  `UBATCH_SIZE=1024`, `--spec-draft-n-max 3`,
  `--spec-draft-n-min 2`, `--spec-draft-p-min 0.0475`,
  `--ctx-checkpoints 0`.

## Patch Snapshot

Before further source edits, the dirty llama.cpp worktree was snapshotted:

- patch:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260629-llamacpp-current-stack-before-next.patch`
- diffstat:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260629-llamacpp-current-stack-before-next.diffstat`

This snapshot covers the current local llama.cpp experiment stack at detached
HEAD `c926ad098` and should be kept even if later patches are losses.

## Audit Summary

Two read-only code audits converged on the same bottleneck:

- The record verifier LM head is the regular reordered-Q8 full-vocabulary
  `MUL_MAT` path followed by in-graph `ggml_argmax` and compact sampled-ID
  readback. Existing `GGML_OP_MUL_MAT_ARGMAX` routes are separate
  scratch/reduce-heavy kernels and repeatedly lost.
- The current SYCL node profile is dominated by exact target/verifier graph
  cost: full-vocab Q8 LM head first, final-layer BF16 routed gate/up second,
  then Q8 routed gate/up nodes. Host sampler/accept/copy overhead is negligible.
- The BF16 direct `MUL_MAT_ID` path was already retested on the selected-down
  VDR2 stack and lost under the fresh gate. Retrying it is duplicate work.

## Closed Or Low-ROI Lanes

Do not spend more record-search runs on these without a new source mechanism or
fresh profile evidence:

- endpoint `LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX=1` and related top1/reorder
  ncols `MUL_MAT_ARGMAX` variants;
- raw/softcap argmax-only paths, which still pay the full LM-head projection;
- late-head bonus as currently implemented, because the separate one-row head
  graph/scheduler/copy/sync cost outweighed the saved row;
- staged MTP3 split-bonus, no-bonus rows, hcopy skip, skip-stateless accept,
  and small host sampled-ID/copy cleanups;
- p-min, n-min/n-max, thread/poll/frequency, and draft-quant roulette;
- `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_BF16_DIRECT=1`.

Alternate MTP draft quantizations (`Q4_K_M`, `Q5_K_M`, `Q6_K`, `Q8_0`) preserve
target quality because the target verifies accepted tokens, but they already
lost strict fresh-response screens. Keep `Q4_0-MTP` as the default draft unless
a future source change changes verifier/draft economics.

## Remaining Plausible Work

1. **Regular-Q8 LM-head top1 epilogue is closed for this implementation.** The
   first prototype (`LLAMA_SPEC_VERIFY_REGULAR_MMVQ_TOP1_EPILOGUE=1` +
   `LLAMA_SYCL_MUL_MAT_TOP1_EPILOGUE=1`) passed strict128 quality but lost the
   primary metric (`111.89` vs `112.52 tok/s` paired control). It also lacked
   an explicit activation counter in the first run, but a follow-up node-profile
   confirmed activation:
   `MUL_MAT_ARGMAX:spec_verify_regular_mmvq_top1_epilogue_token_rows` at
   ~`1.325 ms/call`, still the top node. Do not run full512 on this route
   unless the backend epilogue itself is materially redesigned. A material
   partial-reduction redesign was tried next and also lost (`107.10 tok/s`
   vs `116.82 tok/s` paired control). See
   `20260629-regular-mmvq-top1-epilogue-negative.md` and
   `20260629-regular-mmvq-top1-partial-negative.md`.
2. **Dense/shared BF16 gate/up + GEGLU epilogue is skipped for now.** The
   follow-up top1 node profile did **not** show a visible dense/shared FFN
   gate/up or standalone GEGLU node in the hot set. The hot BF16 item was the
   routed MoE `MUL_MAT_ID:ffn_moe_gate_up-29`, and the routed
   `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_BF16_DIRECT=1` family is already closed
   as a loss. Do not code the dense/shared `build_ffn()` fusion unless a future
   profile shows dense/shared BF16 work near the top.
3. **Upstream SYCL harvest.** Post-`c926ad098` upstream contains SYCL MoE and
   memcpy fixes, but the obvious commits reviewed so far mostly target prefill,
   cross-device copies, or K-quant MoE support rather than this single-GPU Q8
   short-decode hot path. Do not cherry-pick them into the dirty stack unless a
   specific diff maps to the profile.

## Validation Rules

Diagnostic runs may use profiling or synthetic prompts, but a promoted result
must use the fixed realistic cold suite:

- each prompt once;
- `cached_tokens=0` for every request;
- no prompt/KV/context/response/n-gram/history reuse;
- target model and quant unchanged;
- speculative/MTP accepted tokens verified by the target model;
- primary metric is median generated-token throughput for tokens 1-100 after
  TTFT, with p10/mean/TTFT/wall/full512 and hashes/logs retained.
