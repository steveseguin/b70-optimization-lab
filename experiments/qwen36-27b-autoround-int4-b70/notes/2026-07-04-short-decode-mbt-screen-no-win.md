# 2026-07-04 - Qwen27 short-decode max-batched-tokens screen no-win

## Summary

`MAX_NUM_BATCHED_TOKENS` was screened for the current webhie/BF16-scale
INT8-LM-head MTP3/cg8 short-decode recipe because vLLM warns that
`max_num_scheduled_tokens` is set from speculative-decoding settings and can
be suboptimal if the batch-token budget is too small.

The screen did not find a new record. `1536`, `2048`, and `4096` all passed
the strict fresh gate with `cached_tokens=0`, but all landed below the current
`65.27648650325429 tok/s` record. The `1024` same-window control is invalid
because GPU0 hit `UR_RESULT_ERROR_DEVICE_LOST` during the first benchmark
request after smoke passed.

## Runs

Common recipe:

- model: `webhie/Qwen3.6-27B-int4-AutoRound`
- revision: `f5750c90b3776db658594df5fe8051098226dd8e`
- mode: TP1, one B70, vLLM/XPU, XPU graph on
- spec: `qwen3_next_mtp`, `num_speculative_tokens=3`
- graph: `{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}`
- env: `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1`,
  `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`,
  `VLLM_XPU_LM_HEAD_INT8=1`,
  `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16`
- gate: fixed Qwen realistic suite, each prompt once, token IDs requested,
  no history/cache reuse, `cached_tokens=0` required

Results:

| Label | MBT | Status | Median tok/s | p10 | Mean | TTFT median |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| `qwen27-webhie-bf16scale-mbt1024-control-20260704T161806Z` | 1024 | invalid: device lost during bench | n/a | n/a | n/a | n/a |
| `qwen27-webhie-bf16scale-mbt1536-20260704T161806Z` | 1536 | strict fresh pass | `63.82884770312812` | `58.82208591808988` | `63.96286159837782` | `634.2885060003027 ms` |
| `qwen27-webhie-bf16scale-mbt2048-20260704T161806Z` | 2048 | strict fresh pass | `64.23888032762443` | `57.48806912471292` | `63.79231270271783` | `635.2096620248631 ms` |
| `qwen27-webhie-bf16scale-mbt4096-20260704T161806Z` | 4096 | strict fresh pass | `64.77933982738773` | `57.774927255908` | `64.7911516780769` | `632.4908820679411 ms` |

Compact summaries:

- `../../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-mbt1024-control-20260704T161806Z-candidate-summary-20260704T161806Z.json`
- `../../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-mbt1536-20260704T161806Z-candidate-summary-20260704T161806Z.json`
- `../../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-mbt2048-20260704T161806Z-candidate-summary-20260704T161806Z.json`
- `../../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-mbt4096-20260704T161806Z-candidate-summary-20260704T161806Z.json`

Raw run directories are under:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/
```

The failed `1024` control server log shows:

```text
RuntimeError: level_zero backend failed with error: 20 (UR_RESULT_ERROR_DEVICE_LOST)
```

Immediate post-failure `xpu-smi discovery` still saw all four B70s, and
`xpu-smi health -d 0..3` reported power/frequency OK for all devices.

## Interpretation

Do not change the short-decode recipe to `MAX_NUM_BATCHED_TOKENS=1536`, `2048`,
or `4096`. `4096` is the best completed row in this screen, but it is still
below the current record and inside normal recipe variance. It remains useful
for the separate 32K service/prompt-processing lane, where prior long-context
screens found `4096` preferable, but it is not a short-decode headline win.

The failed `1024` row is an operations artifact, not evidence that `1024` is
bad. Existing strict support rows already cover the default `1024` recipe.

## Next action

Keep the short-decode record recipe at `MAX_NUM_BATCHED_TOKENS=1024` unless a
future source change alters graph shapes or scheduler token demand. Continue
optimization on mechanisms that can actually reduce work or improve verified
tokens per target step:

1. reduce LM-head calls/rows before dense full-vocab GEMM;
2. find a oneDNN/XPU-integrated top-ID or candidate-score epilogue;
3. build a materially stronger legal drafter/branching design.
