# Filled-Long Prompt Shape Control

Date: 2026-06-23
Owner/agent: Codex
GPU / port: GPUs 0-3 / `18260..18263`

## Hypothesis

The approved 42.716 tok/s LocalMaxxing result used `BENCH_PROMPT_MODE=long`,
which forces a 512-token response but only uses a short prompt. A near-512-token
input may change decode speed and can expose prefill or KV-cache behavior that
the short-prompt sustained-decode result hides.

## Run Identity

Shared identity:

- model repo: `unsloth/gemma-4-26B-A4B-it-GGUF`
- filename: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- file bytes: `27,636,230,944`
- runtime: llama.cpp `dec5ca557`
- backend: SYCL/Level Zero
- precision: `UD-Q8_K_XL`, f16 KV
- context: `8192`
- API mode: chat/completions
- canary: `CANARY_REPEATS=32` (`128` rows)
- benchmark: `BENCH_PROMPT_MODE=filled-long`, `PROMPT_TOKENS=512`,
  `MAX_TOKENS=512`, `BENCH_REPEATS=4`
- actual benchmark shape: `588` prompt tokens, `512` completion tokens
- shared env: `GGML_SYCL_DISABLE_OPT=0`, `FLASH_ATTN=off`,
  `REASONING=off`, `--parallel 1 --cache-ram 0` unless noted

## Results

| Label | Delta | Canary | Prompt | Output | tok/s after TTFT | tok/s wall | Decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-filledlong-control-20260623T1015` | control, `BATCH=512`, `UBATCH=64`, `POLL=50` | 128/128 | 588 | 512 | 41.140 | 38.710 | no record |
| `gemma4-q8-gpu1-filledlong-poll100-20260623T1015` | `POLL=100` | 128/128 | 588 | 512 | 41.008 | 38.575 | slower |
| `gemma4-q8-gpu2-filledlong-ub128-20260623T1015` | `UBATCH=128` | 128/128 | 588 | 512 | 40.948 | 37.426 | slower |
| `gemma4-q8-gpu3-filledlong-b1024-20260623T1015` | `BATCH=1024` | 128/128 | 588 | 512 | 41.153 | 38.699 | tiny non-record edge |

## Decision

No LocalMaxxing submission. The best filled-prompt shape result is ~41.15 tok/s
after TTFT, below the current approved short-prompt sustained-decode record
(`42.716 tok/s`, 75 input / 512 output). `BATCH_SIZE=1024` is the best of this
screen but only by ~0.013 tok/s over control, which is not enough to promote.

Keep `filled-long` for honest p512/o512-ish comparisons and use `long` only
when measuring short-prompt sustained decode.

## Artifacts

- `data/gemma4-q8-gpu0-filledlong-control-20260623T1015/summary.json`
- `data/gemma4-q8-gpu1-filledlong-poll100-20260623T1015/summary.json`
- `data/gemma4-q8-gpu2-filledlong-ub128-20260623T1015/summary.json`
- `data/gemma4-q8-gpu3-filledlong-b1024-20260623T1015/summary.json`
