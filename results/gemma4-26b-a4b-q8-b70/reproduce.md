# Reproduce Gemma 4 26B A4B Q8 Baseline

These commands set up the first llama.cpp/SYCL baseline. They do not delete any
Qwen models or modify the dirty Qwen vLLM source tree.

## 1. Build llama.cpp with SYCL

```bash
cd /home/steve/qwen36-results-main
scripts/build-llama-cpp-sycl-b70.sh
```

Default output:

```text
/home/steve/src/llama.cpp/build-sycl-b70/bin/llama-server
/home/steve/src/llama.cpp/build-sycl-b70/bin/llama-cli
/home/steve/src/llama.cpp/build-sycl-b70/bin/llama-bench
```

## 2. Download Q8 GGUF

```bash
cd /home/steve/qwen36-results-main
scripts/download-gemma4-26b-q8-gguf.sh
```

The downloader uses resumable `curl` when available and reads Hugging Face
credentials from the local secret files documented in `AGENTS.md`. It falls
back to `huggingface_hub` if curl fails.

Default output:

```text
/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf
```

## 3. Launch One Replica

```bash
cd /home/steve/qwen36-results-main
GPU_INDEX=0 PORT=18260 CTX_SIZE=8192 UBATCH_SIZE=64 \
  scripts/run-gemma4-26b-llamacpp-replica.sh
```

Use `CTX_SIZE=32768` only after the 8K baseline fits and passes canaries. Keep
`CACHE_TYPE_K=f16 CACHE_TYPE_V=f16` for the quality baseline before trying q8 KV.
The launcher defaults `REASONING=off` so exact-answer speed canaries receive
direct chat content; thinking-enabled mode is a separate follow-up profile.

In another shell:

```bash
python3 scripts/gemma4-text-canary.py \
  --base-url http://127.0.0.1:18260 \
  --model gemma4-26b-a4b-q8 \
  --repeats 32 \
  --out data/gemma4-26b-a4b-q8-b70-canary-smoke.json
```

Then run a decode probe:

```bash
python3 scripts/bench-openai-single-decode.py \
  --base-url http://127.0.0.1:18260 \
  --model gemma4-26b-a4b-q8 \
  --prompt-tokens 512 \
  --max-tokens 512 \
  --repeats 8 \
  --out data/gemma4-26b-a4b-q8-b70-smoke.json
```

For the first local baseline, the wrapper below starts the server, waits for
readiness, runs both gates, and stops the server:

```bash
cd /home/steve/qwen36-results-main
scripts/run-gemma4-26b-first-baseline.sh
```

Validated conservative baseline:

```text
label: gemma4-26b-q8-llamacpp-gpu0-ctx8192-20260623T052850Z
canary: 128/128 chat rows pass
p512/o512: 26.10 tok/s after TTFT, 24.24 tok/s wall
summary: data/gemma4-26b-q8-llamacpp-gpu0-ctx8192-20260623T052850Z/summary.json
server log: /mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-26b-q8-llamacpp-gpu0-ctx8192-20260623T052850Z.server.log
```

## 4. Launch Four Replicas

```bash
cd /home/steve/qwen36-results-main
scripts/run-gemma4-26b-llamacpp-quad.sh
```

Ports default to `18260`, `18261`, `18262`, and `18263`, mapped to
`level_zero:0..3`.

## 5. Promote A Result

Before adding to the result table:

1. save the benchmark JSON under `data/`;
2. copy or link the server logs from `/mnt/fast-ai/bench-results/...`;
3. update [validity-gates.md](validity-gates.md) if the gate changed;
4. update [README.md](README.md) with the result status;
5. commit the docs/scripts/data packet.
