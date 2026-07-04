# 2026-07-04 `--language-model-only` Screen

Goal: test whether disabling multimodal inputs on the Qwen3.6 27B AutoRound
text-only serving path improves strict fresh-response throughput or TTFT without
changing model weights, quantization, prompt policy, or target-verified MTP
semantics.

Common identity:

- model:
  `/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e`;
- one B70, TP1, vLLM/XPU;
- `MAX_MODEL_LEN=2048`, `MAX_NUM_BATCHED_TOKENS=1024`;
- `qwen3_next_mtp`, `NUM_SPECULATIVE_TOKENS=3`;
- `COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}'`;
- `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1`;
- `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`;
- `VLLM_XPU_LM_HEAD_INT8=1`;
- `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16`;
- strict Qwen realistic suite, chat mode, each prompt once, `cached_tokens=0`,
  `return_token_ids=true`.

## Why it was plausible

The model architecture is `Qwen3_5ForConditionalGeneration` and the local vLLM
implementation skips the visual tower when `language_model_only` is enabled:

- `vllm/model_executor/models/qwen3_5.py` only constructs `self.visual` if
  `not multimodal_config.language_model_only`;
- the flag is available as `--language-model-only`;
- the control server logs still initialize multimodal processing warnings, while
  the candidate logs `All limits of multimodal modalities supported by the model
  are set to 0, running in text-only mode.`

## Same-window control

Command delta: current record recipe, no extra args.

- run dir:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-int8lmhead-bf16scale-lmonly-control-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260704T050813Z`;
- result:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-lmonly-control-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260704T050813Z.json`;
- gate: pass, `cached_tokens_all_zero=true`;
- median tokens 1-100 after TTFT: `65.81322913235502 tok/s`;
- p10 / mean: `53.10949281819389` / `63.953276218549284`;
- median TTFT: `604.7913415823132 ms`;
- model load: `19.02 GiB`, `9.383657 s`.

The control is within the current record family and is support only, not a new
record claim.

## Candidate

Command delta:

```bash
VLLM_EXTRA_ARGS='--language-model-only'
```

- run dir:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-int8lmhead-bf16scale-lmonly-candidate-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260704T050814Z`;
- no result JSON was produced;
- server did not become HTTP-ready;
- model load improved to `18.15 GiB`, `8.445057 s`;
- available KV cache increased to `9.87 GiB` / `24,849` tokens;
- failure mode: the engine hung for more than eight minutes at:

```text
Capturing CUDA graphs (decode, PIECEWISE):   0%|          | 0/1
```

The run was terminated manually after the control had completed and the
candidate remained non-ready.

## Decision

Closed as **no-win / compatibility issue** for the current MTP3/cg8 strict
record recipe.

`--language-model-only` is useful information for service-memory accounting
because it saves about `0.87 GiB` of model memory on this checkpoint, but it is
not a valid throughput or TTFT optimization in the current XPU graph + MTP path:
decode graph capture hangs before the endpoint becomes ready.

Do not retest this flag as a headline lane unless one of these changes first:

- XPU decode graph capture behavior changes in vLLM;
- MTP is disabled for a pure service-memory/max-context experiment;
- the test is explicitly about non-graph or non-spec serving, with the result
  labeled separately from the current strict decode record.
