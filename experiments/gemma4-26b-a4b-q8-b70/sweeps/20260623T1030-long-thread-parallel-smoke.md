# Long Prompt Thread / Parallel Smoke

Date: 2026-06-23
Owner/agent: Codex
GPU / port: GPUs 0-3 / `18260..18263`

## Hypothesis

The current sustained-decode record uses the short `long` benchmark prompt
(about 75 input tokens, 512 output tokens). Host thread count and llama.cpp
`--parallel` scheduling might move single-session decode rate without changing
the model or precision.

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
- benchmark: `BENCH_PROMPT_MODE=long`, `PROMPT_TOKENS=512`,
  `MAX_TOKENS=512`, `BENCH_REPEATS=4`
- actual benchmark shape: `75` prompt tokens, `512` completion tokens
- shared env: `GGML_SYCL_DISABLE_OPT=0`, `FLASH_ATTN=off`,
  `REASONING=off`, `BATCH_SIZE=512`, `UBATCH_SIZE=64`, `POLL=50`,
  f16 KV

## Results

| Label | Delta | Canary | Prompt | Output | tok/s after TTFT | tok/s wall | Decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-long-t4-20260623T1030` | `THREADS=4`, `--parallel 1 --cache-ram 0` | 128/128 | 75 | 512 | 42.591 | 41.203 | no record |
| `gemma4-q8-gpu1-long-t8-20260623T1030` | `THREADS=8`, `--parallel 1 --cache-ram 0` | 128/128 | 75 | 512 | 42.350 | 40.991 | slower |
| `gemma4-q8-gpu2-long-t32-20260623T1030` | `THREADS=32`, `--parallel 1 --cache-ram 0` | 128/128 | 75 | 512 | 42.597 | 41.208 | no record |
| `gemma4-q8-gpu3-long-parallel2-cache0-20260623T1030` | `THREADS=16`, `--parallel 2 --cache-ram 0` | 128/128 | 75 | 512 | 42.687 | 41.292 | tiny non-record edge |

## Decision

No LocalMaxxing submission. The best variant in this round
(`THREADS=16`, `--parallel 2 --cache-ram 0`) reached `42.687` tok/s after TTFT,
which is close to but still below the current approved sustained-decode record
(`42.716` tok/s). Host thread count is effectively saturated; use `THREADS=16`
unless a future source/runtime change gives a reason to retest it.

The useful result is negative: more CPU threads and `--parallel 2` do not unlock
the next speed tier for single-session decode. Further work should move to build
or source-level changes (AOT BMG, fused Gemma/MoE kernels, vLLM INT8 baseline),
not more host-thread tuning.

## Artifacts

- `data/gemma4-q8-gpu0-long-t4-20260623T1030/summary.json`
- `data/gemma4-q8-gpu1-long-t8-20260623T1030/summary.json`
- `data/gemma4-q8-gpu2-long-t32-20260623T1030/summary.json`
- `data/gemma4-q8-gpu3-long-parallel2-cache0-20260623T1030/summary.json`
