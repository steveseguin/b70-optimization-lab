# 2026-07-05 - Qwen top-token plumbing: dense producer no-win

## Context

The Qwen27 INT4 AutoRound lane is not done at `65.27648650325429 tok/s`.
The goal remains a real `100+ tok/s` strict fresh-response result if the model
and hardware can support it. The current bottleneck evidence points at the
verifier/draft LM-head/logits path: the record family pays about `4.18`
LM-head/logits calls per verifier step, and dense logits cost roughly
`10.6 ms` per verifier step.

Existing vLLM plumbing already has a consumer path for target top-token IDs:

- `gpu_model_runner.py` gates `VLLM_XPU_SPEC_GREEDY_TOP_IDS`;
- `rejection_sampler.py` can verify speculative candidates from precomputed
  target argmax IDs plus bonus IDs;
- `LogitsProcessor.get_top_tokens()` computes local top IDs but still calls the
  dense LM-head producer first.

The test here added the missing Qwen model methods:

- `Qwen2ForCausalLM.get_top_tokens()`;
- `Qwen3_5MTP.get_top_tokens()`.
- `Qwen3NextMTP.get_top_tokens()` was also restored afterward for coverage of
  the adjacent MTP class. This is groundwork only; it does not change the
  conclusion because the current producer still computes dense logits first.

Patch snapshot:

- `patches/qwen36-27b-autoround-int4-b70/vllm-qwen-top-tokens-plumbing-dense-no-win-20260705.patch`

## Strict fresh-response runs

All rows used the fixed realistic Qwen suite, one cold request per prompt,
`cached_tokens=0` on every row, `return_token_ids=true`, and the current
webhie/BF16-scale INT8 LM-head MTP3/cg8 recipe unless noted.

| Run | Median tok/s 1-100 after TTFT | p10 | Mean | Gate |
| --- | ---: | ---: | ---: | --- |
| Same-binary control | `66.05153909520094` | `58.24828834397495` | `65.00747022150018` | pass |
| `VLLM_XPU_SPEC_GREEDY_TOP_IDS=1` target top IDs | `63.46891679585201` | `56.87373383145189` | `63.382594036354355` | pass |
| target top IDs + draft `use_local_argmax_reduction=true` | `64.91951265832384` | `58.19992114695708` | `63.789837529069935` | pass |

Evidence:

- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int4-scratchpad-ring0-control-20260705-20260705T024028Z.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-topids-target-only-20260705-20260705T030215Z.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-topids-target-draft-localargmax-20260705-20260705T030215Z.json`

## Interpretation

The consumer path works and the runs are valid, but this is not a speed win.
`get_top_tokens()` still pays:

1. dense `lm_head.quant_method.apply(...)`;
2. full local logits materialization;
3. an additional `max(dim=-1)` / token-ID path.

So this result does **not** close the LM-head bottleneck and should not be
promoted or submitted. Keep the model-method plumbing only as groundwork for a
future true producer-integrated path behind a default-off flag such as
`VLLM_XPU_LM_HEAD_INT8_TOP_IDS=1`.

## Next action

Do not repeat dense top-token plumbing as an optimization. The next credible
`100+ tok/s` work has to remove real step cost:

1. reduce LM-head calls/rows in the verifier path while keeping exact target
   verification; or
2. build a producer-integrated top-ID/candidate-score primitive that avoids
   full `[rows, vocab]` logits materialization; or
3. materially improve accepted tokens per verifier step with a stronger fresh
   draft source that does not use warmed history/cache effects.
