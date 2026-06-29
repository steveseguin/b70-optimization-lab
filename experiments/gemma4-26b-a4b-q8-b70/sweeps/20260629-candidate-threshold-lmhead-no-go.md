# 2026-06-29 candidate-threshold LM-head no-go

Purpose: decide whether to implement a default-off
`LLAMA_SPEC_VERIFY_CANDIDATE_THRESHOLD_HEAD=1` verifier LM-head op for the
Gemma 4 26B A4B Q8 record stack.

No source edits were made for this decision.

## Current record anchor

- Record: `115.8466634928202 tok/s` median generated-token throughput for
  tokens 1-100 after TTFT.
- Evidence:
  `data/gemma4-q8-gpu1-selecteddown-bf16retest-control-full512-20260629T051323Z/summary.json`.
- Stack: UD-Q8_K_XL target/verifier, Q4_0 MTP draft, VDR2 reordered Q8
  selected-down fused weighted sum, `n_max=3`, `n_min=2`, `p_min=0.0475`,
  `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1`,
  `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`, and
  `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`.

## Row mapping audit

Normal MTP verifier batches are constructed in
`tools/server/server-context.cpp`:

- `handle_last_sampled_token()` appends the last accepted token first, then the
  draft tokens (`sampled`, `draft[0]`, `draft[1]`, ...), and marks those rows
  as output in the normal bonus-row path.
- `spec_i_batch` has `n_draft + 1` rows: verifier rows for the draft tokens plus
  the bonus row.
- `common_sampler_sample_and_accept_n()` compares verifier sampled row `i`
  against `draft[i]` for `i < n_draft`; if all draft rows match, it samples the
  final bonus row.

So, for the standard all-output verifier batch:

- LM-head output row `0` predicts `draft[0]`, which is input token row `1`;
- output row `1` predicts `draft[1]`, which is input token row `2`;
- output row `n_draft - 1` predicts `draft[n_draft - 1]`;
- output row `n_draft` is the bonus row and has no draft candidate inside the
  same target batch.

This means candidate IDs can be derived from shifted `inp_tokens` only for
rows `0..n_draft-1`; the bonus row still needs normal exact top1.

## Decision

Do **not** implement this as the next record attempt.

The row mapping is a narrow **plumbing go** for the standard verifier shape:
`t_inp_tokens[r + 1]` gives the draft candidate for verifier row `r`, and no
new graph input is needed while `n_outputs == n_tokens` and every verifier row
is emitted.

The performance case is still a **record-lane no-go**. Exact speculative
verification needs the true target token on the first mismatch, not merely a
boolean "candidate won" result. A correct candidate-threshold LM-head must
therefore still scan the full vocabulary and track the best challenger/top1 for
every verifier row. That is effectively the same hard part as the
already-closed top1 epilogue and partial-reduction attempts:

- `20260629-regular-mmvq-top1-epilogue-negative.md`;
- `20260629-regular-mmvq-top1-partial-negative.md`;
- `20260629-compact-argmax-reorder-ncols-negative.md`.

The current record path already avoids host-side full-logit transfer via
backend sampled IDs. The remaining hot cost is the full-vocabulary Q8 LM-head
dot work itself. A candidate-vs-max wrapper does not remove that dot work under
exact semantics.

## What would make this worth revisiting

Only reopen this lane if a future design removes verifier LM-head rows or
reduces the full-vocab dot work itself while preserving exact target-model
verification. Examples:

- fold a row-adaptive verifier decision into the existing target decode boundary
  without a second graph/head launch;
- use a mathematically exact bound that proves the candidate wins without
  scanning all vocab rows;
- change the verifier batch shape so fewer LM-head rows are required while the
  bonus-token pipeline remains intact.

Do not spend another implementation pass on a kernel that still performs full
vocab dot products plus top1/challenger reduction for the same rows.
