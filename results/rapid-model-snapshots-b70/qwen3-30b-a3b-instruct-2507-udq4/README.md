# Qwen3 30B-A3B Instruct 2507 UD-Q4_K_XL Rapid Snapshot

Audience: benchmark readers and future optimizers who need the first
strict-valid one-B70 llama.cpp baseline for this model.

## Status

- Model: `unsloth/Qwen3-30B-A3B-Instruct-2507-GGUF`
- File: `Qwen3-30B-A3B-Instruct-2507-UD-Q4_K_XL.gguf`
- HF revision: `eea7b2be5805a5f151f8847ede8e5f9a9284bf77`
- Local path:
  `/mnt/usb-models/llm-models/qwen3-30b-a3b-instruct-2507-gguf/Qwen3-30B-A3B-Instruct-2507-UD-Q4_K_XL.gguf`
- File size verified: `17690497440` bytes
- Runtime: llama.cpp SYCL / Intel Level Zero, one Intel Arc Pro B70
- Binary version: `llama-server version: 9763 (dec5ca557)`, built with
  IntelLLVM 2026.0.0
- Source snapshot recorded by the runner: `/home/steve/src/llama.cpp`
  `fdb1db877c526ec90f668eca1b858da5dba85560`, clean at run time
- Result status: strict-valid rapid snapshot; useful first-pass baseline, not a
  deeply optimized model-specific lane.
- LocalMaxxing: approved as `cmr6rr2kv008imn019frg0x3m`.
  Queue:
  `experiments/rapid-model-snapshots-b70/localmaxxing/qwen3-30b-a3b-instruct-2507-udq4-llamacpp-realistic128-20260704.queue.json`.
  Response:
  `data/localmaxxing-responses/qwen3-30b-a3b-instruct-2507-udq4-llamacpp-realistic128-20260704.submit.log`.

## Headline Strict Row

Use the plain cache-disabled recipe as the representative row. A few sub-percent
runtime variants landed near `108 tok/s`, but did not repeat beyond noise.

- Evidence:
  `data/rapid-model-snapshots-b70/qwen3-30b-a3b-instruct-2507-udq4-llamacpp-faon-nocacheprompt-realistic128-20260704T193409Z.json`
- Raw run directory:
  `/mnt/fast-ai/bench-results/rapid-model-snapshots-b70/runs/qwen3-30b-a3b-instruct-2507-udq4-llamacpp-faon-nocacheprompt-realistic128-20260704T193409Z`
- Primary metric: `107.48388363267362 tok/s` median generated-token throughput
  for tokens 1-100 after TTFT
- p10: `106.89774398673791 tok/s`
- mean: `104.9928121456826 tok/s`
- full after-TTFT median: `107.42138731528047 tok/s`
- wall-clock full-output median: `94.11829410198766 tok/s`
- TTFT median: `166.9534610118717 ms`
- Prompt cache: disabled per request with `{"cache_prompt":false}`
- `cached_tokens=0` on all `12/12` prompts
- `realistic_final_gate.passed=true`

Same-recipe / same-family support rows:

- default control repeats: `107.30658179008877`, `106.89284651799716`, and
  `107.57429935010515 tok/s`;
- no-win runtime variants:
  - `UBATCH_SIZE=512`: `107.54224523986244 tok/s`;
  - `BATCH_SIZE=512 UBATCH_SIZE=256`: `107.57676831837645 tok/s`;
  - `POLL=0`: `108.00493036986039 tok/s`, but repeat was only
    `106.14230746788732 tok/s`;
  - `POLL=100`: `107.91107494975213 tok/s`;
  - `POLL=100 UBATCH_SIZE=1024`: `107.7549851070201 tok/s`;
  - `POLL=100 UBATCH_SIZE=1024 THREADS=16`: `106.82098090127226 tok/s`;
  - `POLL=100 UBATCH_SIZE=1024 GGML_SYCL_ENABLE_VMM=0`:
    `106.83445113088449 tok/s`.

Conclusion: keep the simple default recipe for this rapid result. The quick
screen found no reproducible knob win worth changing the recipe.

## Reproduce

```bash
cd /home/steve/llm-optimizations

MODEL=/mnt/usb-models/llm-models/qwen3-30b-a3b-instruct-2507-gguf/Qwen3-30B-A3B-Instruct-2507-UD-Q4_K_XL.gguf \
MODEL_ALIAS=qwen3-30b-a3b-instruct-2507-udq4-rapid \
LABEL=qwen3-30b-a3b-instruct-2507-udq4-llamacpp-faon-nocacheprompt-realistic128 \
GPU_INDEX=0 PORT=19630 \
CTX_SIZE=4096 BATCH_SIZE=1024 UBATCH_SIZE=256 \
FLASH_ATTN=on CACHE_TYPE_K=f16 CACHE_TYPE_V=f16 \
MAX_TOKENS=128 METRIC_TOKENS=100 \
scripts/run-rapid-llamacpp-realistic-candidate.sh
```

The runner defaults `REQUEST_EXTRA_JSON` to `{"cache_prompt":false}` for
llama.cpp rapid strict runs. Do not remove that for headline claims; the first
diagnostic run with llama.cpp's default prompt-cache behavior reported
`cached_tokens=3` after the first prompt and is invalid for fresh-response
throughput.

## Validity

This row uses the shared rapid realistic suite:

- `repro/rapid-model-snapshots-b70/realistic-suite-v1.json`;
- one cold response per prompt;
- `temperature=0`;
- no speculation, no n-gram/history acceleration, no response reuse;
- no context checkpoints;
- per-request llama.cpp prompt cache disabled;
- `cached_tokens=0` for every request.

The benchmark uses streamed text/reasoning deltas for token timing because
llama.cpp does not provide vLLM-style streamed token IDs here. All rows emitted
enough streamed deltas for the 100-token metric window.

## Blocked vLLM/GPTQ Path

The official `Qwen/Qwen3-30B-A3B-GPTQ-Int4` file was downloaded and validated
locally under:

```text
/mnt/usb-models/llm-models/qwen3-30b-a3b-gptq-int4
```

It did not serve on the current local vLLM/XPU build. Startup failed before
readiness because the build lacks GPTQ ops such as `_C.gptq_shuffle`,
`gptq_gemm`, `gptq_marlin_repack`, and `marlin_gemm`. This is a runtime-support
blocker, not a benchmark result. A later recovery lane should try a newer
Intel/vLLM XPU build or container before dismissing GPTQ for this model.
