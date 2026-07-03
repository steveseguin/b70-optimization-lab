# 2026-07-03: current best reconfirmation and variance update

## Why

After EAGLE3 and DFlash experiments caused several `UR_RESULT_ERROR_DEVICE_LOST`
failures, the current valid MTP3 promote-source recipe was re-run across all
four B70s to confirm the baseline still reproduces and to refresh the variance
floor for future comparisons.

## Recipe

Current promoted recipe:

```bash
QWEN36_27B_ENABLE_MTP=1
NUM_SPECULATIVE_TOKENS=3
QWEN36_27B_ENABLE_XPU_GRAPH=1
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}'
MAX_MODEL_LEN=2048
MAX_NUM_BATCHED_TOKENS=1024
MAX_NUM_SEQS=1
GPU_MEMORY_UTILIZATION=0.95
VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1
VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0
scripts/run-qwen36-27b-autoround-vllm-candidate.sh
```

Fixed Qwen realistic suite, chat mode, one cold response per prompt,
`cached_tokens=0`, streamed token IDs, primary metric = generated tokens 1-100
after TTFT.

## Results

Timestamp family: `20260703T122649Z`.

| GPU | Status | Median tok/s | p10 tok/s | Mean tok/s | Notes |
| --- | --- | ---: | ---: | ---: | --- |
| 0 | invalid/crash | n/a | n/a | n/a | `UR_RESULT_ERROR_DEVICE_LOST` in `_prepare_inputs`, `num_accepted_tokens_event.synchronize()` |
| 1 | pass | `52.836` | `47.737` | `54.059` | `cached_tokens=0` |
| 2 | pass | `53.048` | `47.918` | `54.285` | `cached_tokens=0` |
| 3 | pass | `52.865` | `47.807` | `54.083` | `cached_tokens=0` |

Result files:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-mtp3-promotesource-reconfirm-gpu1-realistic128-chat-tokenids-qwensuite-20260703T122649Z.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-mtp3-promotesource-reconfirm-gpu2-realistic128-chat-tokenids-qwensuite-20260703T122649Z.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-mtp3-promotesource-reconfirm-gpu3-realistic128-chat-tokenids-qwensuite-20260703T122649Z.json
```

GPU0 failure directory:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-mtp3-promotesource-reconfirm-gpu0-realistic128-chat-tokenids-qwensuite-20260703T122649Z
```

GPU0 crash signature:

```text
RuntimeError: level_zero backend failed with error: 20 (UR_RESULT_ERROR_DEVICE_LOST)
gpu_model_runner.py:_prepare_inputs
self.num_accepted_tokens_event.synchronize()
scheduled_spec_decode_tokens={...: [-1, -1, -1]}
```

## Variance Update

Healthy GPUs 1-3:

- mean of medians: `52.916 tok/s`;
- stdev of medians: `0.115 tok/s`;
- range: `0.212 tok/s`;
- range as percent of mean: `0.40%`.

Interpretation:

- The current recipe still reproduces and remains the active baseline family.
- The previously submitted conservative record (`53.522 tok/s`) remains valid,
  but current same-window controls on healthy GPUs are closer to `52.9-53.1`.
- For immediate source-patch comparisons, use same-window controls on GPUs 1-3
  and treat deltas below about `1%` as inconclusive unless repeated/crossover
  runs agree.
- Do not use GPU0 for precision comparisons until it passes a fresh speculative
  control again. `xpu-smi discovery` still enumerates all four B70s after the
  crash, but GPU0 has now device-lost more than once in speculative decode.

## Benchmark Policy Reminder

This reconfirmation remains policy-compliant because it used unique fixed-suite
prompts, one cold response per prompt, streamed token-id timing, and
`cached_tokens=0` on every completed request. The invalid GPU0 lane produced no
result JSON and is not a performance row.
