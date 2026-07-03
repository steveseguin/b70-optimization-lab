# Qwen3.6 27B AutoRound Repro

This repro folder is a bring-up entry point, not a promoted speed record. The
TP1 service smoke passes, but no headline throughput result exists yet.

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

Promote this folder to a full repro only after a baseline benchmark passes the
validity gate in
`../../results/qwen36-27b-autoround-int4-b70/validity-gates.md`.

## Realistic Suite

`realistic-suite-v1.json` is the Qwen27 copy of the fixed cold-response suite
used for promotion-style checks. It intentionally uses the same practical
prompt shapes as the Gemma lane, but has its own suite ID:

```text
qwen36-27b-autoround-int4-b70-realistic-v1
```

Diagnostic invocation against a running service:

```bash
python3 scripts/bench-openai-realistic-suite.py \
  --base-url http://127.0.0.1:19410 \
  --model qwen36-27b-int4-autoround \
  --suite repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json \
  --max-tokens 128 \
  --metric-tokens 100 \
  --request-extra-json '{"chat_template_kwargs":{"enable_thinking":false}}'
```
