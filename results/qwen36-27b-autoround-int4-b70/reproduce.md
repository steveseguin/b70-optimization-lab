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

## Serve One Replica

Initial conservative smoke profile:

```bash
cd /home/steve/llm-optimizations
GPU_INDEX=0 PORT=19410 MAX_MODEL_LEN=2048 \
  experiments/qwen36-27b-autoround-int4-b70/scripts/serve-vllm.sh
```

By default the script uses `qwen3_next_mtp` with
`NUM_SPECULATIVE_TOKENS=2`, matching the model card. Disable speculation while
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

## Next Baseline Steps

After the first smoke passes:

1. Run a no-spec baseline with `QWEN36_27B_ENABLE_MTP=0`.
2. Run the model-card MTP baseline with `NUM_SPECULATIVE_TOKENS=2`.
3. Scale the same recipe to four independent GPUs, one process per B70, to
   support parallel screening.
4. Only then add a fixed realistic prompt suite and LocalMaxxing payload.
