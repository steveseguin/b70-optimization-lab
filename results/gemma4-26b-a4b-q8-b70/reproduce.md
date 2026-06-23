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

Default output:

```text
/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf
```

## 3. Launch One Replica

```bash
cd /home/steve/qwen36-results-main
GPU_INDEX=0 PORT=18260 scripts/run-gemma4-26b-llamacpp-replica.sh
```

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
