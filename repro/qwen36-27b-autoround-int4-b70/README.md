# Qwen3.6 27B AutoRound Repro

This repro folder is the current Qwen3.6 27B AutoRound INT4 one-B70 entry
point. It covers the initial smoke and the current strict fresh-response
benchmark recipe.

## Model

- `Intel/Qwen3.6-27B-int4-AutoRound`
- revision `abc86de19eb1ebbf6a7df4582341325c22ddcb7d`
- AutoRound INT4, `bits=4`, `group_size=128`, symmetric,
  `packing_format=auto_round:auto_gptq`

## Bring-Up

```bash
cd /home/steve/llm-optimizations
experiments/qwen36-27b-autoround-int4-b70/scripts/download-model.sh
GPU_INDEX=0 PORT=19410 MAX_MODEL_LEN=2048 \
  experiments/qwen36-27b-autoround-int4-b70/scripts/serve-vllm.sh
```

In another shell:

```bash
cd /home/steve/llm-optimizations
BASE_URL=http://127.0.0.1:19410/v1 MODEL=qwen36-27b-int4-autoround \
  experiments/qwen36-27b-autoround-int4-b70/scripts/smoke-openai.sh
```

Known passed smoke:

- server log:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/servers/tp1-gpu0-port19410-20260703T012317Z.log`;
- smoke JSON:
  `../../data/qwen36-27b-autoround-openai-smoke-20260703T013020Z.json`;
- MTP2 acceptance after smoke/manual probes: `105/108` accepted draft tokens.

## Current Valid Best

Current best strict result:

- TP1, one B70, Intel checkpoint revision
  `abc86de19eb1ebbf6a7df4582341325c22ddcb7d`;
- vLLM/XPU chat endpoint, XPU graph on, `qwen3_next_mtp`,
  `num_speculative_tokens=3`;
- `COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}'`;
- `MAX_NUM_BATCHED_TOKENS=1024`, `MAX_MODEL_LEN=2048`, thinking disabled;
- `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1`;
- `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`;
- Qwen realistic suite, each prompt once, `cached_tokens=0` for all 12
  requests, `return_token_ids=true`;
- conservative median `53.522 tok/s` for generated tokens 1-100 after TTFT,
  p10 `48.406`, mean `53.986`, TTFT median `628.9 ms`.

Evidence:

```text
../../data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-promotesource-noacceptedpost-repeat2-realistic128-chat-tokenids-qwensuite-20260703T044519Z.json
../../results/qwen36-27b-autoround-int4-b70/promote-source-noacceptedpost-20260703.json
```

## Fastest Quality-Gated Variant

The fastest current practical variant is separate from the original
BF16-LM-head AutoRound quantization:

- label: `webhie AutoRound W4A16 + runtime INT8 LM-head (BF16 scales)`;
- patch:
  `../../patches/qwen36-27b-autoround-int4-b70/vllm-active-stack-with-lmhead-bf16-scale-20260703.patch`;
- env delta: `VLLM_XPU_LM_HEAD_INT8=1` and
  `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16`;
- strict fresh median: `65.276 tok/s`, p10 `59.609`, mean `65.077`,
  `cached_tokens=0`;
- supporting BF16-scale rows: `65.005` and `64.864 tok/s`;
- FP32-scale controls: `64.234` and `64.090 tok/s`; prior submitted webhie
  INT8-LM-head row: `64.306 tok/s`;
- full quality: `pass_all=true`, `baseline_match_all=true`, 1K long-context
  needle passed;
- packet:
  `../../results/qwen36-27b-autoround-int4-b70/webhie-int8-lmhead-bf16scale-20260703.json`.

For the exact current max-throughput row, leave `VLLM_XPU_LM_HEAD_INT8_SCOPE`
unset (default `all`) and set `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16`.
For service/max-context experiments, `VLLM_XPU_LM_HEAD_INT8_SCOPE=target`
remains an attribution idea, not a promoted webhie BF16-scale service recipe:
the older Intel-checkpoint target-only lane passed quality at `61.898 tok/s`,
but the webhie BF16-scale target-only follow-up failed repeat32 once
(`blue, green, red`). Revalidate target-only for the exact checkpoint/revision
and scale dtype before use. See
`../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-03-int8-lmhead-scope-attribution.md`
and
`../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-03-scale-scope-followup-no-headline-win.md`.

Run one strict check for this variant:

```bash
cd /home/steve/llm-optimizations
LABEL=qwen27-webhie-int8lmhead-bf16scale-mtp3-cg8-realistic128-chat-tokenids-qwensuite \
MODEL_DIR=/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e \
GPU_INDEX=0 PORT=19410 \
VLLM_XPU_LM_HEAD_INT8=1 \
VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16 \
scripts/run-qwen36-27b-autoround-vllm-candidate.sh
```

Run a target-only service experiment (diagnostic until it passes a matching
quality gate):

```bash
cd /home/steve/llm-optimizations
LABEL=qwen27-int8lmhead-targetonly-mtp3-cg8-realistic128-chat-tokenids-qwensuite \
GPU_INDEX=0 PORT=19410 \
VLLM_XPU_LM_HEAD_INT8=1 \
VLLM_XPU_LM_HEAD_INT8_SCOPE=target \
scripts/run-qwen36-27b-autoround-vllm-candidate.sh
```

Run the full quality gate after a speed pass:

```bash
cd /home/steve/llm-optimizations
MODEL_DIR=/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e \
GPU_INDEX=0 PORT=19410 MAX_MODEL_LEN=2048 MAX_NUM_BATCHED_TOKENS=1024 \
  QWEN36_27B_ENABLE_MTP=1 NUM_SPECULATIVE_TOKENS=3 \
  QWEN36_27B_ENABLE_XPU_GRAPH=1 \
  VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1 \
  VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0 \
  VLLM_XPU_LM_HEAD_INT8=1 \
  VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16 \
  COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}' \
  experiments/qwen36-27b-autoround-int4-b70/scripts/serve-vllm.sh

/home/steve/.venvs/vllm-xpu/bin/python scripts/qwen36-text-quality-suite.py \
  --base-url http://127.0.0.1:19410 \
  --model qwen36-27b-int4-autoround \
  --tokenizer /mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e \
  --repeat-runs 32 \
  --long-context-tokens 1024 \
  --chat-template-kwargs-json '{"enable_thinking":false}' \
  --baseline-json data/qwen36-27b-autoround-int4-b70-baselines/quality-webhie-int8lmhead-mtp3-cg8-repeat32-ctx1024-20260703T170941Z.json
```

## Realistic Suite

`realistic-suite-v1.json` is the Qwen27 copy of the fixed cold-response suite
used for promotion-style checks. It intentionally uses the same practical
prompt shapes as the Gemma lane, but has its own suite ID:

```text
qwen36-27b-autoround-int4-b70-realistic-v1
```

Launch the current best service:

```bash
cd /home/steve/llm-optimizations
MODEL_DIR=/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e \
GPU_INDEX=0 PORT=19410 MAX_MODEL_LEN=2048 MAX_NUM_BATCHED_TOKENS=1024 \
  QWEN36_27B_ENABLE_MTP=1 NUM_SPECULATIVE_TOKENS=3 \
  QWEN36_27B_ENABLE_XPU_GRAPH=1 \
  VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1 \
  VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0 \
  VLLM_XPU_LM_HEAD_INT8=1 \
  VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16 \
  COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}' \
  experiments/qwen36-27b-autoround-int4-b70/scripts/serve-vllm.sh
```

Run the strict realistic-suite gate against that service:

```bash
python3 scripts/bench-openai-realistic-suite.py \
  --base-url http://127.0.0.1:19410 \
  --model qwen36-27b-int4-autoround \
  --api-mode chat \
  --suite repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json \
  --max-tokens 128 \
  --metric-tokens 100 \
  --return-token-ids \
  --request-extra-json '{"chat_template_kwargs":{"enable_thinking":false}}'
```

The primary metric comes from streamed token-id receipt timestamps. Text chunks
are grouped and must not be treated as token counts.
