# 2026-07-05 - Draft INT4 separate-head speed screen is promising but invalid

## Context

Current promoted Qwen27 strict/fresh record remains
`webhie/Qwen3.6-27B-int4-AutoRound + runtime INT8 LM-head BF16 scales`,
MTP3/cg8, one B70, target-verified, `cached_tokens=0`, median
`65.27648650325429 tok/s`.

The next credible lane was to reduce draft LM-head cost. The target verifier
LM-head must stay exact, but the draft is allowed to be approximate if the
target still verifies and the hybrid GDN state remains equivalent.

## Patch Under Test

Patch snapshots:

- `patches/qwen36-27b-autoround-int4-b70/vllm-draft-lmhead-int4-separate-draft-head-20260705.patch`
- `patches/qwen36-27b-autoround-int4-b70/vllm-draft-lmhead-int4-separate-draft-head-current-20260705.patch`
- `patches/qwen36-27b-autoround-int4-b70/vllm-draft-lmhead-int4-lowmargin-fallback-20260705.patch`

Main source changes:

- `vllm/model_executor/layers/vocab_parallel_embedding.py`
  prepares a default-off draft-only INT4 LM-head path gated by
  `VLLM_XPU_DRAFT_LM_HEAD_INT4=1`.
- `vllm/v1/spec_decode/llm_base_proposer.py` keeps the MTP draft LM-head
  separate when the draft head has `_xpu_lm_head_int4_weight_t`; otherwise the
  usual Qwen MTP weight-sharing path overwrites the draft INT4 buffer and the
  test is not measuring the intended path.

## Results

Speed-only screen after the MTP head-sharing fix:

- label: `qwen27-webhie-targetint8-draftint4-mtp3-cg8-sharefix-20260705A`
- strict fresh median: `72.80342913586986 tok/s`
- mean: `72.29800185864879 tok/s`
- p10: `65.66255156329277 tok/s`
- gate mechanics: fixed Qwen realistic suite, unique prompts, each prompt once,
  `cached_tokens=0`, no prefix/history/cache reuse
- status: **diagnostic only**, because it did not have a matching passing
  quality run

Quality run with the same mechanism:

- label: `qwen27-webhie-targetint8-draftint4-g128-quality-20260705A`
- strict fresh median: `70.29695361249847 tok/s`
- exact short cases: pass
- long/needle: pass
- repeat/order: **fail**
- status: **invalid**, not promotable and not LocalMaxxing-eligible

Closed variants:

- group size `64`: `72.66735105697835 tok/s`, speed-only, no quality pass
- group size `256`: `72.16534112433177 tok/s`, speed-only, no quality pass
- FP32 scales: `71.80885842461203 tok/s`, speed-only, no quality pass
- state/postprocess matrix: all repeat/order failed
- no-async and graph-off diagnostics: repeat/order still failed
- spec top-token plumbing: repeat/order still failed
- low-margin exact fallback (`0.5/1/2/4`): repeat/order still failed and speed
  fell to `61.5/59.2/56.2/53.1 tok/s`

## Interpretation

The INT4 draft head is a real speed signal, but it is not valid yet. The
failure is not simply graph replay, async scheduling, the accepted-state
postprocess shortcut, or a low-confidence top-1 draft row. Those were tested
and still failed.

The likely blocker is deeper: changing the draft proposal distribution changes
the MTP accept/reject pattern, and the current Qwen/GDN state accounting is not
equivalent for those arbitrary patterns. The target verifier can still verify
tokens, but hybrid GDN/DeltaNet running state must also be advanced/rolled back
exactly. The repeat/order failures (`blue, green, red`, repeated yellow, etc.)
look like non-equivalent state transitions rather than ordinary sampling drift.

## Next Implementation Direction

Do not submit or promote the draft-INT4 result. Continue implementation in this
order:

1. Add or use focused trace hooks for the failing repeat/order case:
   draft IDs, target IDs, accepted counts, bonus row decisions, full/partial
   accept events, and GDN state snapshot/restore/commit stages.
2. Compare a passing exact-draft run against the failing INT4-draft run on the
   same repeat canary to identify the first divergent accept/reject/state event.
3. Fix GDN state equivalence for arbitrary proposal patterns, not just the
   current exact shared-draft pattern. Candidate fixes include accepted-prefix
   replay/tape semantics, stricter restore-before-commit ordering, or disabling
   only the unsafe state shortcut for the specific divergent pattern.
4. Only after repeat/order passes should the `~70-73 tok/s` draft-INT4 path
   be rerun on the strict fresh suite and considered for promotion.

## Policy

This lane is diagnostic until quality passes. It must not be advertised as a
fresh-response record, and it must not be submitted to LocalMaxxing.
