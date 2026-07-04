# 2026-07-04 - Draft Top-K64 Diagnostic and Sequential Reranker Limit

## Summary

The Qwen27 draft top-k lane is now bounded strongly enough to avoid another
cheap reranker endpoint attempt. A full 96-prompt fresh-response diagnostic with
draft top-64 tracing shows that the target verifier token is almost always
inside the draft model's top-64 alternatives, but simple held-out reranking
rules still do not improve accepted tokens/step, and the apparently large
independent top-k oracle is not directly implementable in the current
sequential MTP proposer.

The practical conclusion is unchanged but better supported:

- do **not** ship or endpoint-test a post-hoc top-k reranker;
- do **not** treat independent per-position top-k oracles as speed claims;
- future accepted-token work needs a real stronger drafter, branch/regenerate
  path, or target-matched training design that preserves sequential MTP
  semantics and target-owned bonus behavior.

## Run Identity

Label:
`qwen27-webhie-bf16scale-drafttopk64-eaglechat96-20260704T152429Z`

Model:
`webhie/Qwen3.6-27B-int4-AutoRound`, revision
`f5750c90b3776db658594df5fe8051098226dd8e`

Runtime:

- one B70 / TP1;
- vLLM XPU graph, `qwen3_next_mtp`, `num_speculative_tokens=3`;
- `max_cudagraph_capture_size=8`;
- `MAX_MODEL_LEN=2048`, `MAX_NUM_BATCHED_TOKENS=1024`;
- `VLLM_XPU_LM_HEAD_INT8=1`;
- `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16`;
- `VLLM_XPU_SPEC_DECODE_VERIFY_TRACE_FILE=.../verify-trace.jsonl`;
- `VLLM_XPU_DRAFT_TOPK_TRACE_FILE=.../draft-topk.jsonl`;
- `VLLM_XPU_DRAFT_TOPK_TRACE_K=64`;
- `RUN_QUALITY=0` (diagnostic run; no quality promotion).

Suite:
`experiments/qwen36-27b-autoround-int4-b70/eagle-chat-corpus-v2-suite.json`

Raw run directory outside Git:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-bf16scale-drafttopk64-eaglechat96-20260704T152429Z
```

Tracked summaries:

- strict runner output:
  `../../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-drafttopk64-eaglechat96-20260704T152429Z-realistic128-chat-tokenids-qwensuite-20260704T152429Z.json`;
- candidate summary:
  `../../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-drafttopk64-eaglechat96-20260704T152429Z-candidate-summary-20260704T152429Z.json`;
- top-k64 join analysis:
  `../../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-drafttopk64-eaglechat96-20260704T152429Z-draft-topk64-analysis.json`;
- top-k64 reranker evaluation:
  `../../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-drafttopk64-eaglechat96-20260704T152429Z-draft-topk64-reranker-eval.json`.

## Fresh-Response Validity

The benchmark harness passed the strict fresh gate mechanically:

- `96` unique prompts;
- each prompt sent once;
- `cached_tokens=0` on every request;
- `return_token_ids=true`;
- no prompt/KV/cache/history or response reuse.

The measured median was only `52.13988222517163 tok/s` for generated tokens
1-100 after TTFT. This is **diagnostic only**, because full draft top-64 tracing
adds heavy JSONL logging and is not representative of the current record recipe.
Do not submit or advertise this speed.

## K64 Evidence

Top-k64 join analysis:

- aligned verifier steps: `18761`;
- base mean target-verified tokens/step: `2.6243270614572785`;
- independent per-position top-k64 oracle:
  `3.9271360801663024` target tokens/step;
- current draft match rate by position:
  - pos0: `0.7602473215713448`;
  - pos1: `0.6471936463941155`;
  - pos2: `0.5860561803741805`;
- target-in-top64 rate by position:
  - pos0: `0.9966952721070306`;
  - pos1: `0.9835296625979425`;
  - pos2: `0.9676456478865733`.

Prompt/step held-out reranker evaluation:

- split: `step_index_parity` (`9381` train, `9380` test);
- base test mean target tokens/step: `2.626226012793177`;
- independent top-k64 oracle test:
  `3.9242004264392323`;
- final-position-only upper bound with recomputed/branched bonus:
  `2.7872068230277183`;
- best margin rule test: `2.626226012793177` (flat);
- best sparse token-bias rule test: `2.621321961620469` (regression).

The K32 traces had the same shape after relabeling:

- 24-prompt calibration trace: base test `2.703125`, final-slot upper bound
  `2.873263888888889`;
- 96-prompt EAGLE chat trace: base test `2.5930717863105173`, final-slot upper
  bound `2.761686143572621`.

## Interpretation

The target token being in top-k is not enough. Qwen27's current MTP proposer is
sequential: token 1 is generated conditioned on the actual sampled token 0, and
token 2 is generated conditioned on the actual sampled token 1. Replacing token
0 or token 1 after the fact invalidates the later recorded top-k rows. Even
replacing only token 2 invalidates the already-computed target bonus row,
because the bonus row belongs to the target continuation after the original
final draft token.

Therefore:

- the independent top-k64 oracle is only an upper bound for a future
  branch/regenerate/tree drafter or materially stronger trained drafter;
- the final-slot upper bound is closer to implementable, but still requires
  recomputing or branching the target bonus row and only adds about
  `+0.16` target tokens/step on this held-out trace, below the `+0.25` target
  worth endpoint work;
- margin and sparse-bias rerankers did not improve held-out acceptance, so a
  cheap rule-based endpoint patch is closed.

## Script/Artifact Hygiene

The diagnostic scripts were updated so future summaries do not overstate this:

- `scripts/analyze-qwen27-draft-topk-trace.py` now labels the old oracle as
  `oracle_topk_independent_upper_bound` and keeps the previous scalar key only
  as deprecated compatibility;
- `scripts/evaluate-qwen27-draft-topk-rerankers.py` now emits both
  `oracle_topk_independent_upper_bound` and
  `oracle_topk_last_position_recomputed_bonus_upper_bound`, with explicit
  runtime interpretation text.

The older K32 analysis/eval JSONs were regenerated with the corrected labels.

## Decision

Closed as a no-endpoint diagnostic lane. Do not submit anything to
LocalMaxxing. The next credible accepted-token work is not another reranker
sweep; it is either:

1. a real target-matched drafter/training lane that improves held-out accepted
   tokens materially before endpoint testing; or
2. a correct branch/regenerate/tree-verifier design that can legally use top-k
   alternatives without invalidating later draft rows or the target-owned bonus.
