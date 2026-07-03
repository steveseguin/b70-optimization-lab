# Qwen3.6 27B MTP GGUF Q4 Handoff

Last updated: 2026-07-03

Use this file when resuming the Unsloth GGUF Q4/MTP lane.

## Do Not Mix With

- `results/qwen36-27b-autoround-int4-b70/`: Intel AutoRound INT4 vLLM/XPU.
- `results/qwen36-35b-quark-int8-b70/`: Qwen35 Quark W8A8.
- `results/gemma4-26b-a4b-q8-b70/`: Gemma Q8 llama.cpp production lane.

This lane has its own checkpoint, quantization format, runtime, and result
identity.

## Current Bring-Up / Result

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

Completed as of this note:

1. Hugging Face GGUF download completed.
2. One-GPU server smoke passed with exact JSON and `cached_tokens=0`.
3. Strict fresh-response no-spec versus `draft-mtp` comparison completed.
4. Parallel MTP/config sweep completed on GPUs 1-3.

Conclusion: this GGUF lane is valid but not competitive. Best strict row is
`30.679 tok/s` median generated-token throughput for tokens 1-100 after TTFT,
while the Intel AutoRound vLLM lane is `53.522 tok/s` under the same Qwen
realistic policy. Treat the GGUF lane as a preserved fallback/reference, not
the active path unless a new source-level llama.cpp Qwen/GDN idea appears.

Build status:

- AOT B70 build completed and reports llama.cpp `9860 (fdb1db877)` when oneAPI
  is sourced.
- JIT SYCL fallback build completed.
- If invoking `llama-server` directly, source `/opt/intel/oneapi/setvars.sh`
  first. A raw shell can fail with `libsvml.so` missing.
- Launcher now defaults to one server slot with `N_PARALLEL=1` / `-np 1`;
  keep that for single-session decode comparisons.

## Best Repro Commands

```bash
cd /home/steve/llm-optimizations

GPU_INDEX=1 PORT=19431 \
  ENABLE_MTP=1 MTP_N_MAX=3 MTP_N_MIN=0 MTP_P_MIN=0.00 \
  scripts/serve-qwen36-27b-mtp-gguf-llamacpp.sh
```

Then run the Qwen realistic suite against the OpenAI-compatible endpoint:

```bash
BASE_URL=http://127.0.0.1:19431 \
  LABEL=llamacpp-mtp3-aot-np1-realistic128 \
  REQUEST_EXTRA_JSON='{}' \
  scripts/bench-qwen36-27b-mtp-gguf-realistic.sh
```

The one-shot candidate runner starts, waits, benchmarks, and kills a temporary
server:

```bash
GPU_INDEX=1 PORT=19431 \
  LABEL=llamacpp-mtp3-aot-np1-realistic128 \
  MTP_N_MAX=3 MTP_N_MIN=0 MTP_P_MIN=0.00 \
  scripts/run-qwen36-27b-mtp-gguf-candidate.sh
```

Do not pass vLLM-only `chat_template_kwargs` to llama.cpp. The server launcher
sets `--reasoning off`; the benchmark wrapper defaults to
`REQUEST_EXTRA_JSON='{}'`.

## Closed Initial Knobs

All of these passed the fresh gate but were no-wins versus the best GGUF row:

- `MTP_N_MAX=4` and `MTP_N_MAX=5`;
- `MTP_N_MIN=2 MTP_P_MIN=0.0475`;
- `UBATCH_SIZE=512` and `UBATCH_SIZE=1024`;
- `POLL=100` plus `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`;
- `GGML_SYCL_ENABLE_VMM=0`;
- `FLASH_ATTN=off`;
- `CACHE_TYPE_K=q8_0 CACHE_TYPE_V=q8_0`.

Evidence summary: `initial-realistic-sweep-20260703.json`.
