# Reproduce Qwen3.6 27B AutoRound Bring-Up

## Download

```bash
cd /home/steve/llm-optimizations
experiments/qwen36-27b-autoround-int4-b70/scripts/download-model.sh
```

The script reads the Hugging Face token from
`/home/steve/.config/huggingface/token` if present and downloads into the
shared cache under `/mnt/fast-ai/llm-cache/hf`. The token is never stored in the
repo.

## Serve Current Best One-Replica Result

Current strict/fresh best profile:

```bash
cd /home/steve/llm-optimizations
GPU_INDEX=0 PORT=19410 MAX_MODEL_LEN=2048 MAX_NUM_BATCHED_TOKENS=1024 \
  QWEN36_27B_ENABLE_MTP=1 NUM_SPECULATIVE_TOKENS=3 \
  QWEN36_27B_ENABLE_XPU_GRAPH=1 \
  VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1 \
  VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0 \
  COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}' \
  experiments/qwen36-27b-autoround-int4-b70/scripts/serve-vllm.sh
```

The two `VLLM_XPU_GDN_*` env vars are the current validated speed delta: the
forward metadata reads the accepted speculative slot as the running source, so
the separate accepted-state postprocess copy can be disabled without dropping
the recurrent-state transition.

Initial conservative smoke / model-card profile is still available by omitting
the env delta and using the script defaults. Disable speculation while
debugging loader correctness with:

```bash
QWEN36_27B_ENABLE_MTP=0 GPU_INDEX=0 PORT=19410 MAX_MODEL_LEN=2048 \
  experiments/qwen36-27b-autoround-int4-b70/scripts/serve-vllm.sh
```

## Smoke

With the server running:

```bash
cd /home/steve/llm-optimizations
BASE_URL=http://127.0.0.1:19410/v1 MODEL=qwen36-27b-int4-autoround \
  experiments/qwen36-27b-autoround-int4-b70/scripts/smoke-openai.sh
```

The smoke is intentionally small. It checks `/v1/models`, one deterministic
chat completion, non-empty output, visible text, and basic degeneration
signals. Promotion requires the stricter gate in `validity-gates.md`.

The smoke disables Qwen thinking by default with
`chat_template_kwargs={"enable_thinking": false}`. Set `ENABLE_THINKING=1` only
when intentionally testing the reasoning field; the normal bring-up smoke
expects a non-empty OpenAI `content` field.

Known passed smoke:

```text
data/qwen36-27b-autoround-openai-smoke-20260703T013020Z.json
server log: /mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/servers/tp1-gpu0-port19410-20260703T012317Z.log
```

Summary:

- `pass=true`;
- content: `{"answer": 42, "unit": "widgets"}`;
- `finish_reason=stop`;
- `completion_tokens=14`, `prompt_tokens=45`;
- server metrics after smoke/manual probes: `105/108` MTP draft tokens
  accepted.

## Strict Gate

Run the fixed realistic suite:

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

Current conservative evidence is:

```text
../../data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-promotesource-noacceptedpost-repeat2-realistic128-chat-tokenids-qwensuite-20260703T044519Z.json
```

Median `53.522 tok/s` for generated tokens 1-100 after TTFT, p10 `48.406`,
mean `53.986`, `cached_tokens=0` for all 12 prompts, quality suite pass and
baseline match:

```text
../../data/qwen36-27b-autoround-int4-b70-baselines/quality-promotesource-noacceptedpost-mtp3-cg8-repeat32-ctx1024-20260703T043946Z.json
```
