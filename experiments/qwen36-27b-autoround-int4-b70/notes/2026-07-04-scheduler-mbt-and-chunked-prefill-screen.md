# 2026-07-04 Scheduler MBT / Chunked-Prefill Screen

Goal: run one bounded four-GPU same-window scheduler screen on the current
webhie BF16-scale INT8-LM-head record recipe, then stop unless there is a clear
strict-gate improvement outside variance.

This is a config screen, not a record claim. It was justified by the vLLM log
warning:

```text
max_num_scheduled_tokens is set to 1024 based on the speculative decoding settings.
This may lead to suboptimal performance. Consider increasing max_num_batched_tokens...
```

Common identity:

- model:
  `/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e`;
- one B70 per replica, TP1, vLLM/XPU;
- `MAX_MODEL_LEN=2048`;
- `qwen3_next_mtp`, `NUM_SPECULATIVE_TOKENS=3`;
- `COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}'`;
- `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1`;
- `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`;
- `VLLM_XPU_LM_HEAD_INT8=1`;
- `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16`;
- strict Qwen realistic suite, chat mode, each prompt once, `cached_tokens=0`,
  `return_token_ids=true`.

## Results

| lane | GPU | status | median tok/s 1-100 after TTFT | p10 | mean | TTFT median | artifact |
| --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| control MBT1024 | 0 | invalid: device lost after 11 prompts | `63.87687620304972` (incomplete) | `54.98811033032026` | `63.25429840929533` | `606.9629214471206 ms` | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-schedscreen-control1024-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260704T052010Z.json` |
| MBT768 | 1 | pass, `cached_tokens=0` | `64.13138299356905` | `57.73383779515195` | `63.33973899585137` | `608.3270709495991 ms` | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-schedscreen-mbt768-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260704T052010Z.json` |
| MBT1280 | 2 | pass, `cached_tokens=0` | `64.34552061140312` | `58.093086101258415` | `63.56768740524933` | `604.8826350597665 ms` | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-schedscreen-mbt1280-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260704T052010Z.json` |
| no chunked prefill | 3 | invalid before readiness | n/a | n/a | n/a | n/a | run log only |

No-chunked-prefill failure:

```text
This model does not officially support disabling chunked prefill.
...
ValidationError: max_num_batched_tokens (1024) is smaller than max_model_len (2048).
```

Control failure:

```text
RuntimeError: level_zero backend failed with error: 20 (UR_RESULT_ERROR_DEVICE_LOST)
```

The control row still emitted an incomplete JSON with 11 completed prompts, but
it is not valid evidence because the gate did not complete.

## Decision

Closed as **no-win**:

- `MAX_NUM_BATCHED_TOKENS=768` and `1280` both pass the strict fresh gate, but
  both are below the approved `65.27648650325429 tok/s` record and below recent
  same-recipe controls around `65.8 tok/s`;
- `--no-enable-chunked-prefill` is invalid for the current `MAX_MODEL_LEN=2048`
  / `MAX_NUM_BATCHED_TOKENS=1024` serving mode and vLLM warns this model does
  not support disabling chunked prefill;
- no LocalMaxxing submission and no follow-up repeat/crossover are warranted.

Keep `MAX_NUM_BATCHED_TOKENS=1024` and chunked prefill enabled for the current
short-context decode record recipe.
