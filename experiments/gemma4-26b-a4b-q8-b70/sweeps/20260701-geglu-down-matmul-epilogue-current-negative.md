# 2026-07-01 - GEGLU Down Matmul Epilogue Current-Stack Screen

Status: closed negative. No LocalMaxxing submission.

## Goal

Re-test the default-off `LLAMA_GEMMA4_MOE_GEGLU_DOWN_MATMUL_EPILOGUE=1`
path under the current Gemma 4 26B A4B Q8 record stack. This was the remaining
"post-GEMM GEGLU epilogue" verifier/MoE-cost idea after older GEGLU-before-down
and packed GEGLU variants were already closed as negative or inconclusive.

The test was intended to answer only one question: does this already-present
current-source flag move the strict fresh-response short-decode metric in the
right direction before spending effort on new source work?

## Identity

- source worktree:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926`
- built server:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server`
- source identity: llama.cpp `c926ad098` dirty Gemma optimization stack
- target/verifier model:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft model:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- base recipe: VDR2 selected-down, final post-norm fusion, FA on, 32K/VMM,
  `n_max=3`, `n_min=2`, `p_min=0.0475`, `BATCH_SIZE=1024`,
  `UBATCH_SIZE=1024`, `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`,
  `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`, no history/ngram/cache reuse
- validation: fixed realistic suite, each prompt once cold,
  `cached_tokens=0` for every row, 128 generated tokens, 100-token primary
  metric window after TTFT, canary repeats `32` (`128` canary rows)

## Runs

```bash
cd /home/steve/qwen36-results-main

# controls
GPU_INDEX=0 PORT=18420 FLASH_ATTN=on CTX_SIZE=32768 \
  GGML_SYCL_ENABLE_VMM=1 MAX_TOKENS=128 CANARY_REPEATS=32 \
  REALISTIC_GATE=1 REALISTIC_METRIC_TOKENS=100 \
  LABEL=gemma4-q8-gpu0-gegludownmat-control-strict128-20260701T061422Z \
  bash repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh

GPU_INDEX=2 PORT=18422 FLASH_ATTN=on CTX_SIZE=32768 \
  GGML_SYCL_ENABLE_VMM=1 MAX_TOKENS=128 CANARY_REPEATS=32 \
  REALISTIC_GATE=1 REALISTIC_METRIC_TOKENS=100 \
  LABEL=gemma4-q8-gpu2-gegludownmat-control-strict128-20260701T061422Z \
  bash repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh

# candidates
GPU_INDEX=1 PORT=18421 FLASH_ATTN=on CTX_SIZE=32768 \
  GGML_SYCL_ENABLE_VMM=1 MAX_TOKENS=128 CANARY_REPEATS=32 \
  REALISTIC_GATE=1 REALISTIC_METRIC_TOKENS=100 \
  LLAMA_GEMMA4_MOE_GEGLU_DOWN_MATMUL_EPILOGUE=1 \
  LABEL=gemma4-q8-gpu1-gegludownmat-on-strict128-20260701T061422Z \
  bash repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh

GPU_INDEX=3 PORT=18423 FLASH_ATTN=on CTX_SIZE=32768 \
  GGML_SYCL_ENABLE_VMM=1 MAX_TOKENS=128 CANARY_REPEATS=32 \
  REALISTIC_GATE=1 REALISTIC_METRIC_TOKENS=100 \
  LLAMA_GEMMA4_MOE_GEGLU_DOWN_MATMUL_EPILOGUE=1 \
  LABEL=gemma4-q8-gpu3-gegludownmat-on-strict128-20260701T061422Z \
  bash repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh
```

## Results

All four runs passed the strict freshness checks:

- realistic gate passed;
- canary passed;
- `cached_tokens_all_zero=true`;
- prompts were unique and each prompt was sent once.

| label | flag | median tok/s 1-100 | p10 | mean | full128 median | TTFT median ms |
|---|---:|---:|---:|---:|---:|---:|
| `gemma4-q8-gpu0-gegludownmat-control-strict128-20260701T061422Z` | off | `119.05514562919211` | `108.34566452639842` | `119.64069818966999` | `120.51443228522186` | `179.57178800133988` |
| `gemma4-q8-gpu2-gegludownmat-control-strict128-20260701T061422Z` | off | `116.97487828110022` | `105.90600389251878` | `116.5344675542113` | `113.9073890041566` | `179.1530919726938` |
| `gemma4-q8-gpu1-gegludownmat-on-strict128-20260701T061422Z` | on | `78.88908260591842` | `69.96527099701746` | `78.95909931116093` | `77.62427191559408` | `194.15506394580007` |
| `gemma4-q8-gpu3-gegludownmat-on-strict128-20260701T061422Z` | on | `76.56989021267371` | `68.24174503126903` | `76.66715824269423` | `74.88630808257571` | `194.0963984816335` |

## Decision

Closed negative. The candidate is semantically valid but much slower than the
paired controls: roughly `-38` to `-42 tok/s` on the primary median metric.

Do not promote, submit, or run full512 for this flag. The likely cause is that
the epilogue path introduces extra routed-row packing / dispatch work that
overwhelms any saved graph nodes under the current small-token MTP verifier
shape. Future work in this area should target a tighter verifier/head path or
a backend-boundary reduction with profile evidence, not this broad GEGLU-down
epilogue route.
