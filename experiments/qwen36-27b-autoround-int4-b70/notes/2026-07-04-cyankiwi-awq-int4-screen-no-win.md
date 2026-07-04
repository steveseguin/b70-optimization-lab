# 2026-07-04 - cyankiwi AWQ INT4 strict screen no-win

## Summary

`cyankiwi/Qwen3.6-27B-AWQ-INT4` was downloaded, loaded successfully in vLLM/XPU
with `--quantization compressed-tensors`, and passed the strict fresh-response
realistic speed gate mechanically, but it is not competitive with the current
`webhie/Qwen3.6-27B-int4-AutoRound + runtime INT8 LM-head BF16 scales` record.

Result:

- strict fresh median tokens 1-100 after TTFT: **56.565477988590345 tok/s**;
- p10: `53.78861033968192`, mean: `57.871755872391134`;
- TTFT median: `600.8212079759687 ms`;
- fixed Qwen realistic suite: 12 unique prompts, each prompt once;
- `cached_tokens=0` on all 12 requests;
- `return_token_ids=true`, metric source `openai_stream_token_ids_chunk_timestamp`;
- smoke passed;
- no LocalMaxxing submission, because this is slower than the current
  `65.27648650325429 tok/s` strict record.

Evidence:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-cyankiwi-awq-int4-int8lmhead-bf16scale-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260704T134357Z.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-cyankiwi-awq-int4-int8lmhead-bf16scale-mtp3-cg8-candidate-summary-20260704T134357Z.json
data/qwen36-27b-autoround-int4-b70-baselines/smoke-qwen27-cyankiwi-awq-int4-int8lmhead-bf16scale-mtp3-cg8-20260704T134357Z.json
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-cyankiwi-awq-int4-int8lmhead-bf16scale-mtp3-cg8-20260704T134357Z/server.stdout.log
```

## Model Artifact

Local standalone model directory:

```text
/mnt/fast-ai/llm-models/qwen36-27b-awq-int4-cyankiwi-8f269fb
```

The four downloaded shard sizes were verified:

```text
model-00001-of-00004.safetensors 5350050984
model-00002-of-00004.safetensors 5341886624
model-00003-of-00004.safetensors 4394614824
model-00004-of-00004.safetensors 5357436848
```

Model metadata:

- architecture: `Qwen3_5ForConditionalGeneration`;
- text hidden size: `5120`;
- vocab size: `248320`;
- `mtp_num_hidden_layers=1`;
- quantization: compressed-tensors `pack-quantized`, W4A16-style AWQ,
  `group_size=32`, asymmetric int weights; linear-attention projections and
  multimodal/visual layers are ignored by the quantization config.

Server log confirms:

- `quantization=compressed-tensors`;
- `XPUwNa16LinearKernel for CompressedTensorsWNA16`;
- target and drafter weights loaded;
- runtime INT8 LM-head BF16 scales prepared for both target and draft
  (`VLLM_XPU_LM_HEAD_INT8=1`, `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16`);
- graph capture completed with `max_cudagraph_capture_size=8`;
- prefix cache hit rate stayed `0.0%` during the strict run.

## Command

```bash
cd /home/steve/llm-optimizations

MODEL_DIR=/mnt/fast-ai/llm-models/qwen36-27b-awq-int4-cyankiwi-8f269fb \
QWEN36_27B_AR_REPO=cyankiwi/Qwen3.6-27B-AWQ-INT4 \
LABEL=qwen27-cyankiwi-awq-int4-int8lmhead-bf16scale-mtp3-cg8 \
SERVED_MODEL_NAME=qwen36-27b-cyankiwi-awq-int4 \
GPU_INDEX=0 PORT=19420 \
MAX_MODEL_LEN=2048 MAX_NUM_BATCHED_TOKENS=1024 MAX_NUM_SEQS=1 \
GPU_MEMORY_UTILIZATION=0.95 \
QWEN36_27B_ENABLE_MTP=1 NUM_SPECULATIVE_TOKENS=3 \
QWEN36_27B_ENABLE_XPU_GRAPH=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}' \
VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1 \
VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0 \
VLLM_XPU_LM_HEAD_INT8=1 \
VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16 \
VLLM_EXTRA_ARGS='--quantization compressed-tensors' \
QWEN36_27B_DEFAULT_ENABLE_THINKING=0 \
QWEN36_27B_ENABLE_PROMPT_TOKEN_DETAILS=1 \
QUALITY_BASELINE_JSON=data/qwen36-27b-autoround-int4-b70-baselines/quality-webhie-int8lmhead-bf16scale-mtp3-cg8-repeat32-ctx1024-20260703T223138Z.json \
RUN_QUALITY=1 READINESS_TIMEOUT_S=1200 \
experiments/qwen36-27b-autoround-int4-b70/scripts/run-vllm-candidate.sh
```

## Harness Fixes Found During This Screen

Two runner issues were fixed as part of this candidate:

1. `COMPILATION_CONFIG="${COMPILATION_CONFIG:-{\"...\":8}}"` emitted malformed
   JSON with an extra `}` because Bash parameter expansion stopped at the JSON
   closing brace. `run-vllm-candidate.sh` and `run-long-context-ladder.sh` now
   assign the JSON default with an explicit `if [[ -z ... ]]` block.
2. `run-vllm-candidate.sh` defaulted to system `python3`; the strict speed
   bench worked, but the quality suite needs `transformers`. The runner now
   defaults to `$QWEN36_27B_AR_VENV/bin/python`, while still allowing explicit
   `PYTHON=...` override.

The quality stage for this AWQ no-win run failed before writing JSON due the
old system-Python default:

```text
ModuleNotFoundError: No module named 'transformers'
```

That does **not** affect the strict speed classification: the speed gate
finished first, passed the fresh/cached-zero policy, and was already far below
the record. If this checkpoint is ever revisited for non-speed reasons, rerun
quality with the fixed runner.

## Interpretation

This checkpoint is mechanically useful as compressed-tensors coverage: it loads,
captures graphs, serves the strict suite, and keeps the policy-critical
fresh-response fields clean. It is not a current optimization path because it is
about `13.3%` slower than the approved webhie/BF16-scale runtime INT8-LM-head
record:

```text
56.565 / 65.276 - 1 = -13.35%
```

Do not repeat this exact AWQ screen unless a source change materially changes
compressed-tensors W4A16 performance, MTP acceptance, or LM-head cost.

## Next Action

No checkpoint-level cheap candidate remains open from the current local audit.
Continue with source mechanisms only if they have a clear stop gate:

- integrated exact LM-head/top-ID producer that helps both draft and target and
  is faster before endpoint validation;
- target-verified verifier row/call reduction that preserves replacement and
  bonus semantics;
- materially stronger target-matched drafter trained/evaluated on held-out
  data;
- DFlash/multi-KV metadata work only if it changes the known assertion/device
  loss failure mode.
