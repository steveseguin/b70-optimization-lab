# 2026-06-30 - SYCL Flash-Attention Scheduler Knobs Screen

Goal: improve Gemma 4 26B A4B Q8 long-context prompt processing without
regressing correctness or short-context decode. This was a service/prefill
screen only, not a LocalMaxxing headline candidate.

## Patch

Snapshot:
`patches/gemma4-26b-a4b-q8-b70/20260630-sycl-fattn-scheduler-knobs-experiment.patch`

The experiment added default-off runtime controls in
`ggml/src/ggml-sycl/fattn-common.hpp`:

- `GGML_SYCL_FATTN_DV512_GQA_STREAM_K=1` to force stream-k for DV512/GQA;
- `GGML_SYCL_FATTN_PARALLEL_BLOCKS=1` to force one KQ parallel block;
- `GGML_SYCL_FATTN_PARALLEL_BLOCKS=-1` to force all KQ tiles.

The source experiment was reverted after the screen. The patch snapshot is kept
so future agents can reproduce or inspect the negative result.

## Validation Setup

Common identity:

- model: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- runtime: llama.cpp Gemma record stack at `/home/steve/src/llama.cpp-gemma-record-repro-c926`;
- GPU mode: one B70 per replica, four lanes in parallel;
- context: `CTX_SIZE=32768`;
- batch/ubatch: `BATCH_SIZE=2048`, `UBATCH_SIZE=2048`;
- attention: `FLASH_ATTN=on`, `GGML_SYCL_ENABLE_VMM=1`;
- GQA selector: `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`;
- cold service gate: `LONG_CONTEXT_GATE=1`,
  `LONG_CONTEXT_CASE_IDS=lc-22000-middle`,
  `LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS=24000`;
- output: `MAX_TOKENS=96`;
- canary: `CANARY_REPEATS=1`;
- cache policy: prompt cache off (`--cache-ram 0`), context checkpoints off
  (`--ctx-checkpoints 0`), and `cached_tokens=0` audited in the long-context
  result rows.

Aggregate result:
`data/gemma4-fattn-schedknobs-20260630Tfattn-schedknobs-A.json`

## Results

| Lane | Validity | Median prefill tok/s | Median decode tok/s | Notes |
| --- | --- | ---: | ---: | --- |
| control | valid service screen | 949.59 | 112.13 | Canary passed, exact long-context JSON passed, `cached_tokens=0`. |
| `GGML_SYCL_FATTN_DV512_GQA_STREAM_K=1` | invalid | n/a | n/a | Failed chat canary immediately with empty JSON output. |
| `GGML_SYCL_FATTN_PARALLEL_BLOCKS=1` | valid but bad tradeoff | 959.36 | 19.58 | Only +1.03% prefill, but long-context decode collapsed. Do not promote. |
| `GGML_SYCL_FATTN_PARALLEL_BLOCKS=-1` | invalid/hung | n/a | n/a | Passed canary but made no long-context progress for over six minutes and was terminated. |

## Decision

Do not promote any scheduler override.

`PARALLEL_BLOCKS=1` is the only lane that preserved validation, but its prefill
gain is too small to matter and its decode regression is severe. Forced
stream-k and all-tiles are correctness/stability failures.

Future work should not repeat these exact knobs unless the attention scheduler
or DV512/GQA kernel changes substantially. Better next targets are broader
prompt-processing ladders that preserve the short decode record, or verifier
cost reductions for the short-context record lane.
