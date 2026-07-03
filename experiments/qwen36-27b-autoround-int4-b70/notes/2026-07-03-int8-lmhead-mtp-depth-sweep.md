# 2026-07-03 INT8 LM-head MTP Depth Sweep

Goal: check whether the quality-passing runtime INT8 LM-head changes the best
internal `qwen3_next_mtp` draft length. Earlier k>3 sweeps were no-win on the
BF16-LM-head lane; the cheaper LM-head projection might have shifted the
acceptance/cost tradeoff.

All lanes used:

- `Intel/Qwen3.6-27B-int4-AutoRound` revision
  `abc86de19eb1ebbf6a7df4582341325c22ddcb7d`;
- one B70, TP1, vLLM/XPU, chat mode, thinking disabled;
- XPU graph on, `COMPILATION_CONFIG={"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}`;
- `MAX_MODEL_LEN=2048`, `MAX_NUM_BATCHED_TOKENS=1024`;
- `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1`;
- `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`;
- `VLLM_XPU_LM_HEAD_INT8=1`;
- fixed Qwen realistic suite, each prompt once, `cached_tokens=0`, token-id
  timing. These are valid fresh-response diagnostics, but not new headline
  records unless they beat the promoted `62.628 tok/s` row and pass quality.

| k | GPU | artifact | gate | median tok/s | p10 | mean | TTFT ms |
| ---: | ---: | --- | --- | ---: | ---: | ---: | ---: |
| 2 | 0 | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int8lmhead-mtp2-cg8-realistic128-chat-tokenids-qwensuite-20260703T135024Z.json` | pass, cached=0 | `59.161535` | `54.677777` | `55.708379` | `432.459` |
| 3 | 1 | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int8lmhead-mtp3-reconfirm-cg8-realistic128-chat-tokenids-qwensuite-20260703T135025Z.json` | pass, cached=0 | `61.921263` | `58.727758` | `62.459772` | `609.481` |
| 4 | 2 | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int8lmhead-mtp4-cg8-realistic128-chat-tokenids-qwensuite-20260703T135025Z.json` | pass, cached=0 | `58.372366` | `51.337458` | `56.927109` | `785.599` |
| 5 | 3 | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int8lmhead-mtp5-cg8-realistic128-chat-tokenids-qwensuite-20260703T135025Z.json` | pass, cached=0 | `57.401488` | `48.851981` | `53.367784` | `990.098` |

Early server metrics matched the result: k4/k5 increased mean accepted length
but lowered per-position acceptance enough that the extra draft LM-head work was
not worthwhile. k3 remains the best depth for this runtime.

Decision:

- keep `NUM_SPECULATIVE_TOKENS=3` for the INT8-LM-head lane;
- do not promote or submit k2/k4/k5;
- do not keep sweeping draft length without a new mechanism that reduces
  per-draft LM-head/top-1 cost.

Next useful work: either harden the runtime INT8 LM-head for service/longer
quality contexts, or build a true fused LM-head top-1 / candidate-bound verifier
that avoids full vocab projection materialization while preserving exact greedy
semantics.
