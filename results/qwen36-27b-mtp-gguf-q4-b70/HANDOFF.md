# Qwen3.6 27B MTP GGUF Q4 Handoff

Last updated: 2026-07-03

Use this file when resuming the Unsloth GGUF Q4/MTP lane.

## Do Not Mix With

- `results/qwen36-27b-autoround-int4-b70/`: Intel AutoRound INT4 vLLM/XPU.
- `results/qwen36-35b-quark-int8-b70/`: Qwen35 Quark W8A8.
- `results/gemma4-26b-a4b-q8-b70/`: Gemma Q8 llama.cpp production lane.

This lane has its own checkpoint, quantization format, runtime, and result
identity.

## Current Bring-Up

- Upstream llama.cpp clean tree:
  `/home/steve/src/llama.cpp`
- Build directory:
  `/home/steve/src/llama.cpp/build-sycl-b70-qwen36-mtp`
- Fallback JIT build directory:
  `/home/steve/src/llama.cpp/build-sycl-b70-qwen36-mtp-jit`
- Launcher:
  `/home/steve/llm-optimizations/scripts/serve-qwen36-27b-mtp-gguf-llamacpp.sh`
- Model path:
  `/mnt/usb-models/models/qwen36-27b-mtp-gguf/Qwen3.6-27B-UD-Q4_K_XL.gguf`

Pending as of this note:

1. Hugging Face GGUF download completion.
2. One-GPU server smoke.
3. No-spec versus `draft-mtp` first strict-suite comparison.

Build status:

- AOT B70 build completed and reports llama.cpp `9860 (fdb1db877)` when oneAPI
  is sourced.
- JIT SYCL fallback build completed.
- If invoking `llama-server` directly, source `/opt/intel/oneapi/setvars.sh`
  first. A raw shell can fail with `libsvml.so` missing.

## First Commands

```bash
cd /home/steve/llm-optimizations

GPU_INDEX=1 PORT=19431 \
  scripts/serve-qwen36-27b-mtp-gguf-llamacpp.sh
```

Then run the Qwen realistic suite against the OpenAI-compatible endpoint:

```bash
python3 scripts/bench-openai-realistic-suite.py \
  --base-url http://127.0.0.1:19431 \
  --model qwen36-27b-mtp-gguf-q4 \
  --api-mode chat \
  --suite repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json \
  --max-tokens 128 \
  --metric-tokens 100 \
  --request-extra-json '{"chat_template_kwargs":{"enable_thinking":false}}' \
  --out data/qwen36-27b-mtp-gguf-q4-b70-baselines/<label>.json
```

If llama.cpp rejects `chat_template_kwargs`, rerun without that request extra
but keep `--reasoning off` in the server launcher.
