# 2026-07-04 - Draft LM-head batching audit and DFlash next blocker

Status: **closed as a quick patch; useful as direction for deeper work**.

Active target:

- `webhie/Qwen3.6-27B-int4-AutoRound`;
- runtime INT8 LM-head with BF16 scales;
- MTP3/cg8, `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1`,
  `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`;
- strict fresh record to beat: `65.27648650325429 tok/s`, LocalMaxxing
  `cmr5iu3gk00bfq901nidgcana`.

## Why this audit happened

Fresh timing says the largest avoidable bucket is LM-head/logits materialization:
about `2258` LM-head/logits calls over `540` verifier steps.  Draft-side calls
are the larger sub-bucket (`~3.1` draft LM-head calls per verifier step), and
rows `1-4` dense oneDNN INT8 LM-head timings are nearly flat, so the obvious
question was:

> Can the three draft LM-head rows in MTP3 be batched into one rows<=3 LM-head
> call?

## Finding: sequential MTP cannot batch the draft rows

For `qwen3_next_mtp`, the draft proposer path in
`/home/steve/src/vllm/vllm/v1/spec_decode/llm_base_proposer.py` is sequential:

1. first draft forward produces `sample_hidden_states`;
2. `_greedy_sample(sample_hidden_states)` picks draft token 0;
3. the loop feeds draft token 0 into the next MTP forward;
4. `_greedy_sample(last_hidden_states[:batch_size])` picks draft token 1;
5. the loop feeds draft token 1 into the next MTP forward;
6. `_greedy_sample(last_hidden_states[:batch_size])` picks draft token 2.

The hidden state for draft token `i+1` does not exist until draft token `i` has
already been sampled and run through the next MTP forward, so there is no set of
three independent draft hidden rows to batch after the fact.  A patch that only
collects hidden rows later cannot preserve the same draft trajectory.

The already-tested `use_local_argmax_reduction` path is also not a rescue.  It
adds/uses `get_top_tokens()` but still computes the full LM-head logits before
the max, and same-window crossover was flat/no-win:

```text
experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-03-draft-local-argmax-no-win.md
```

## What would be required to avoid sequential draft LM-head work

The real architectural alternatives are:

1. a parallel/tree drafter whose candidate hidden states exist in one forward;
2. a stronger learned drafter (EAGLE/DFlash-style) with high enough acceptance;
3. a real fused LM-head top-ID producer that makes each sequential LM-head call
   materially cheaper.

The first two are not config toggles.  Current DFlash is the only local path
that structurally avoids the sequential MTP draft loop, but mixed full/sliding
attention is blocked by single-KV-group assumptions.

## DFlash quick patch is unsafe

`DFlashProposer` currently owns one context slot-mapping buffer and one query
slot-mapping buffer, and `DFlashQwen3Model.precompute_and_store_context_kv()`
writes every DFlash layer using the same `context_slot_mapping`.

Mixed Qwen attention creates multiple KV cache groups.  Removing
`validate_same_kv_cache_group()` alone would be wrong because:

- `DFlashProposer.set_inputs_first_pass()` computes future query slot mappings
  from **one** `cad.block_table_tensor`;
- the runner currently passes the drafter one
  `spec_decode_common_attn_metadata`, selected by `drafter.kv_cache_gid`;
- `slot_mappings` by layer covers the current target tokens, but it does not
  provide future query block tables for bonus/mask tokens in every KV group;
- using group 0's block table for sliding/full groups can silently corrupt the
  draft KV cache, yielding invalid acceptance and invalid benchmark data.

Therefore the minimum correct DFlash mixed-SWA patch needs new plumbing, not an
assert deletion:

1. track `draft_layer_to_kv_cache_gid` and `draft_kv_cache_gids`;
2. build `AttentionGroup`s keyed by `(kv_cache_gid, backend, kv_cache_spec)`;
3. pass drafter-visible `CommonAttentionMetadata` (or at least block tables and
   slot mappings) for every draft KV group, not just one group;
4. compute DFlash context and future-query slot mappings per KV group;
5. update `DFlashQwen3Model.precompute_and_store_context_kv()` to select the
   layer's group-specific context slot mapping;
6. only then run startup smoke and strict fresh validation.

## Decision

Do not spend more time on:

- draft LM-head row batching for sequential MTP3;
- another `get_top_tokens()` / local-argmax wrapper;
- deleting the DFlash single-KV-group assertion.

The next source attempt should either:

- implement the full DFlash multi-KV metadata path above as a dedicated patch
  cycle with startup-only smoke before any speed claim; or
- return to kernel-level LM-head work, but only with a materially different
  primitive than the already-closed full-vocab scan / second-reduction designs.

Any promoted result must still pass the fixed Qwen realistic suite with
`cached_tokens=0`, one cold request per prompt, target-verified speculation,
quality gates, and variance handling before LocalMaxxing submission.
