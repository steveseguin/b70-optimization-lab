# 2026-07-05 - ReplaySSM Commit-In-Forward Skip-Post Screen

Status: **valid quality / no promote**. This is a useful overhead-reduction
screen for the ReplaySSM lane, but it does not beat the current Qwen27 record.
No LocalMaxxing submission.

## Hypothesis

ReplaySSM stage-fix is the only clean draft-INT4 family so far, but prior rows
landed at `61-62 tok/s`, below the `65.27648650325429 tok/s` webhie BF16-scale
INT8-LM-head record. Source audit found that the code already has a
`VLLM_XPU_GDN_REPLAYSSM_COMMIT_IN_FORWARD` path that can commit the pending
tape at the start of the next GDN forward.

Before this screen, enabling that env did not replace the post-verify Python
commit loop; post-verify committed first, so the next-forward path usually saw
`pending=0`. The tested patch skips the separate post-verify commit when
`COMMIT_IN_FORWARD=1` and no draft restore correction is active.

Patch:

- `../../../patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-replayssm-commit-in-forward-skippost-no-promote-20260705.patch`

The active vLLM worktree also contains broader Qwen27 research edits; the patch
above is the isolated delta for this experiment.

## Config

```bash
LABEL=qwen27-draftint4-replayssm-commitforward-skippost-20260705
GPU_INDEX=0 PORT=19420
QUALITY_REPEAT_RUNS=64 QUALITY_SKIP_LONG_CONTEXT=1
VLLM_XPU_GDN_REPLAYSSM_SPEC=1
VLLM_XPU_GDN_REPLAYSSM_SPEC_CACHE_LEN=8
VLLM_XPU_GDN_REPLAYSSM_TORCH_FALLBACK=0
VLLM_XPU_GDN_REPLAYSSM_STAGE_CONV_TORCH_FALLBACK=0
VLLM_XPU_GDN_REPLAYSSM_COMMIT_IN_FORWARD=1
VLLM_XPU_LM_HEAD_INT8=1
VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16
VLLM_XPU_DRAFT_LM_HEAD_INT4=1
VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE=128
VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE=bf16
QWEN36_27B_ENABLE_XPU_GRAPH=1
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}'
QWEN36_27B_ENABLE_MTP=1
NUM_SPECULATIVE_TOKENS=3
experiments/qwen36-27b-autoround-int4-b70/scripts/run-vllm-candidate.sh
```

The candidate runner filename still says `repeat32`, but the JSON contains 64
repeat runs because `QUALITY_REPEAT_RUNS=64` was set.

## Result

Artifacts:

- summary:
  `../../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-replayssm-commitforward-skippost-20260705-candidate-summary-20260705T223056Z.json`
- strict fresh suite:
  `../../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-replayssm-commitforward-skippost-20260705-realistic128-chat-tokenids-qwensuite-20260705T223056Z.json`
- quality:
  `../../../data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-draftint4-replayssm-commitforward-skippost-20260705-repeat32-ctx1024-20260705T223056Z.json`
- smoke:
  `../../../data/qwen36-27b-autoround-int4-b70-baselines/smoke-qwen27-draftint4-replayssm-commitforward-skippost-20260705-20260705T223056Z.json`
- server log:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-draftint4-replayssm-commitforward-skippost-20260705-20260705T223056Z/server.stdout.log`

Strict fresh suite:

- median tokens 1-100 after TTFT: **`63.853743411579195 tok/s`**
- p10 `59.45334694016865`, mean `65.02396189547093`
- full after-TTFT median `66.12327202065987 tok/s`
- TTFT median `478.3138129860163 ms`
- `cached_tokens=0` for all 12 prompts

Quality:

- exact cases passed;
- repeat64 color/order passed;
- baseline comparison passed;
- long-context was skipped for this screen.

## Interpretation

This patch is correctness-safe in the tested ReplaySSM draft-INT4 screen and
recovers some of the ReplaySSM overhead:

- prior draft-INT4 ReplaySSM stage-fix: `61.749` and `62.286 tok/s`;
- commit-in-forward skip-post: `63.854 tok/s`;
- current record: `65.276 tok/s`.

So the idea is useful but not enough to promote. It makes ReplaySSM less
expensive but still does not turn draft-INT4 into the record lane.

Keep the patch as a reference for a future exact tape design. Do not submit it
to LocalMaxxing and do not spend more endpoint runs on ReplaySSM
micro-optimizations unless the goal is specifically to make the valid
ReplaySSM lane match the current record; the `100+ tok/s` route still needs
materially stronger verified drafting or a lower-cost exact state transaction.
