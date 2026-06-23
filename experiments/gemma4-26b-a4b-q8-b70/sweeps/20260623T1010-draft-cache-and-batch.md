# 20260623T1010 Draft Cache And Batch Sweep

Goal: continue from the `90.419 tok/s` `n=7` no-backend-sampling +
`--spec-draft-threads 32` record and test whether draft cache compression or a
larger server batch improves the filled-long MTP lane.

Common identity:

- runtime: llama.cpp `dec5ca557`, SYCL/Level Zero, AOT BMG build
  `/home/steve/src/llama.cpp/build-sycl-b70-aot-bmg-g31/bin/llama-server`;
- model: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: `mtp-gemma-4-26B-A4B-it.gguf`;
- baseline flags: `BENCH_PROMPT_MODE=filled-long`, `MTP_N_MAX=7`,
  `MTP_N_MIN=2`, `MTP_P_MIN=0.10`, `MTP_BACKEND_SAMPLING=0`,
  `MTP_DRAFT_THREADS=32`, `GGML_SYCL_DISABLE_OPT=0`, `FLASH_ATTN=off`,
  `POLL=50`, `--parallel 1 --cache-ram 0`;
- quality gate: `384/384` chat canary before benchmark;
- benchmark shape: actual `588` prompt tokens and `512` output tokens.

## Results

| GPU | Label | Change | Canary | tok/s after TTFT | tok/s wall | Decision |
| --- | --- | --- | --- | ---: | ---: | --- |
| 0 | `gemma4-q8-gpu0-mtp-n7-aot-nmin2-pmin010-nobs-dthreads32-repeat-filled-long-deep-20260623T101000Z` | repeat current record config | 384/384 | 90.259 | 82.230 | Valid repeat, below `90.419`; confirms record is plausible but near noise floor. |
| 1 | `gemma4-q8-gpu1-mtp-n7-aot-nmin2-pmin010-nobs-dthreads32-dv-q8-filled-long-deep-20260623T101000Z` | draft `V` cache `q8_0`, `FLASH_ATTN=off` | 384/384 | 41.247 | 39.427 | Not a valid q8_0-cache test: server logged `V cache quantization requires flash_attn`; falls back near no-spec speed. |
| 2 | `gemma4-q8-gpu2-mtp-n7-aot-nmin2-pmin010-nobs-dthreads32-dkv-q8-filled-long-deep-20260623T101000Z` | draft `K/V` cache `q8_0`, `FLASH_ATTN=off` | 384/384 | 41.043 | 39.237 | Not a valid q8_0-cache test: server logged `V cache quantization requires flash_attn`; falls back near no-spec speed. |
| 3 | `gemma4-q8-gpu3-mtp-n7-aot-nmin2-pmin010-nobs-dthreads32-batch1024-filled-long-deep-20260623T101000Z` | `BATCH_SIZE=1024` | 384/384 | 90.203 | 82.233 | Valid, below record. |

## Takeaways

- Draft cache compression was attempted incorrectly with `FLASH_ATTN=off`.
  llama.cpp logged `V cache quantization requires flash_attn`, so the result is
  useful as a harness/fallback warning but **not** a true q8_0-cache benchmark.
  A proper retest needs `FLASH_ATTN=on`, with the known risk that FA-on has been
  slower in earlier Gemma/B70 sweeps.
- `BATCH_SIZE=1024` does not help single-session decode after TTFT. Keep
  `BATCH_SIZE=512` unless a future long-prefill or concurrency test needs it.
- The current record is close to run-to-run noise: repeat measured `90.259`
  versus `90.419`. Treat future improvements below about `0.3 tok/s` as weak
  unless repeated or backed by a clear mechanism.

## Follow-Up

Next axes should mostly focus on scheduling, plus one proper FA-on q8_0-cache
retest if slots are available:

- `THREADS=32`;
- `MTP_DRAFT_THREADS_BATCH=32`;
- `POLL=75` / `POLL=100`;
- `FLASH_ATTN=on` retest under the final MTP identity;
- `FLASH_ATTN=on` plus draft `V` and `K/V` q8_0 if FA-on itself is not badly
  slower.
