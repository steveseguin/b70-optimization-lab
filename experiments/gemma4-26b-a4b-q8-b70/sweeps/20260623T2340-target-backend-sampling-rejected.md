# 2026-06-23 - target backend sampling for speculative verification rejected

## Goal

Try to remove target-side verifier raw-logit materialization in the Gemma 4
26B A4B Q8 draft-MTP lane. The hypothesis was that enabling llama.cpp backend
sampling for speculative target verification could return verifier token ids
directly and avoid full host logits for every verifier row.

## Proposed patch

Rejected before benchmarking:

- `tools/server/server-context.cpp`: allow `--backend-sampling` for speculative
  slots behind `LLAMA_SPEC_TARGET_BACKEND_SAMPLING=1`.
- `common/sampling.cpp`: check `llama_get_sampled_token_ith(ctx, idx)` before
  `set_logits()` so a backend-sampled token can avoid forcing full raw logits.

The patch was reverted before any run. No result should be counted from this
lane.

## Why it is invalid as-is

Source audit found llama.cpp backend sampling is currently sequence-keyed, not
verifier-row-keyed:

- `llama_context` rejects backend sampling when one sequence has multiple
  output tokens in a batch. Speculative verification intentionally produces
  multiple verifier rows for the same sequence.
- The sequence-to-output-row mapping keeps one row per `seq_id`, so multiple
  verifier rows for the same sequence would overwrite each other even if the
  guard were removed.
- If raw logits were skipped while only one backend token was produced, the
  verifier would either fail with an invalid input batch or read stale/partial
  logits for rows that did not receive backend sampled tokens.

Expected failure mode: `llama_decode()` returns an invalid-batch error before a
valid throughput measurement is possible.

## Next useful direction

This remains a worthwhile upstream design idea, but it needs deeper llama.cpp
support for sampler results keyed by output row, not only by sequence. Until
then, do not use target backend sampling as a headline optimization for
speculative verification.

