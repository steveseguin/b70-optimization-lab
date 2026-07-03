# 2026-07-03 INT8 LM-head XPU Graph Capture-Size Sweep

Goal: check whether the quality-passing runtime INT8 LM-head changes the best
XPU graph capture size. Earlier capture-size sweeps were no-win on the
BF16-LM-head lane, but the logits path changed enough to justify one bounded
retest.

Common identity:

- `Intel/Qwen3.6-27B-int4-AutoRound` revision
  `abc86de19eb1ebbf6a7df4582341325c22ddcb7d`;
- one B70, TP1, vLLM/XPU, chat mode, thinking disabled;
- `qwen3_next_mtp`, `NUM_SPECULATIVE_TOKENS=3`;
- `MAX_MODEL_LEN=2048`, `MAX_NUM_BATCHED_TOKENS=1024`;
- `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1`;
- `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`;
- `VLLM_XPU_LM_HEAD_INT8=1`;
- fixed Qwen realistic suite, each prompt once, `cached_tokens=0`, token-id
  timing.

## First same-window screen

| capture size | GPU | artifact | result |
| ---: | ---: | --- | --- |
| 4 | 0 | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int8lmhead-mtp3-cg4-realistic128-chat-tokenids-qwensuite-20260703T135335Z.json` | pass, median `62.353186`, p10 `53.066676`, mean `59.357600`, TTFT `614.327 ms` |
| 8 | 1 | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int8lmhead-mtp3-cg8-control-realistic128-chat-tokenids-qwensuite-20260703T135335Z.json` | pass, median `62.142981`, p10 `57.299837`, mean `62.460606`, TTFT `617.134 ms` |
| 16 | 2 | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int8lmhead-mtp3-cg16-realistic128-chat-tokenids-qwensuite-20260703T135335Z.json` | invalid: `UR_RESULT_ERROR_DEVICE_LOST` during graph replay |
| 32 | 3 | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int8lmhead-mtp3-cg32-realistic128-chat-tokenids-qwensuite-20260703T135335Z.json` | pass, median `62.821098`, p10 `52.103412`, mean `60.414320`, TTFT `613.776 ms` |

The single cg32 median was slightly above the promoted `62.628` row, but the
p10/mean were worse and the delta was below the known variance band. I ran a
same-window confirmation instead of promoting it.

## cg32 confirmation against cg8 controls

| lane | GPU | artifact | result |
| --- | ---: | --- | --- |
| cg32 repeat A | 0 | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int8lmhead-mtp3-cg32-repeatA-realistic128-chat-tokenids-qwensuite-20260703T135646Z.json` | pass, median `61.398317`, p10 `52.261964`, mean `59.414706`, TTFT `603.604 ms` |
| cg8 control A | 1 | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int8lmhead-mtp3-cg8-controlA-realistic128-chat-tokenids-qwensuite-20260703T135646Z.json` | pass, median `61.879394`, p10 `57.512969`, mean `62.331640`, TTFT `619.879 ms` |
| cg32 repeat B | 2 | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int8lmhead-mtp3-cg32-repeatB-realistic128-chat-tokenids-qwensuite-20260703T135646Z.json` | pass, median `63.157682`, p10 `52.337919`, mean `60.726621`, TTFT `605.192 ms` |
| cg8 control B | 3 | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int8lmhead-mtp3-cg8-controlB-realistic128-chat-tokenids-qwensuite-20260703T135646Z.json` | pass, median `61.976759`, p10 `57.314312`, mean `62.578634`, TTFT `607.088 ms` |

Decision:

- keep `max_cudagraph_capture_size=8`;
- do not promote cg32: its median is noisy, its p10/mean are worse than cg8,
  and it does not reliably beat the existing `62.628 tok/s` record;
- do not use cg16 for this lane: it device-lost under graph replay.

Next useful work is source-level LM-head/top-1 reduction or service hardening,
not more capture-size sweeps.
