# 20260623T1012 Draft Thread Count Sweep

Goal: test whether the `--spec-draft-threads 32` record was below or above the
best thread count for the current filled-long MTP identity.

Common identity:

- runtime: llama.cpp `dec5ca557`, SYCL/Level Zero, AOT BMG build
  `/home/steve/src/llama.cpp/build-sycl-b70-aot-bmg-g31/bin/llama-server`;
- model: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: `mtp-gemma-4-26B-A4B-it.gguf`;
- baseline flags: `BENCH_PROMPT_MODE=filled-long`, `MTP_N_MAX=7`,
  `MTP_N_MIN=2`, `MTP_P_MIN=0.10`, `MTP_BACKEND_SAMPLING=0`,
  `GGML_SYCL_DISABLE_OPT=0`, `FLASH_ATTN=off`, `POLL=50`,
  `BATCH_SIZE=512`, `UBATCH_SIZE=64`, `--parallel 1 --cache-ram 0`;
- quality gate: `384/384` chat canary before benchmark;
- benchmark shape: actual `588` prompt tokens and `512` output tokens.

Current record to beat:

- `gemma4-q8-gpu3-mtp-n7-aot-nmin2-pmin010-nobs-dthreads32-filled-long-deep-20260623T094131Z`;
- `90.41948035379636 tok/s` after TTFT, `82.3415769722187 tok/s` wall;
- LocalMaxxing approved as `cmqqgn3cm0163qo010optg91u`.

## Results

| GPU | Label | Change | Canary | tok/s after TTFT | tok/s wall | Decision |
| --- | --- | --- | --- | ---: | ---: | --- |
| 0 | `gemma4-q8-gpu0-mtp-n7-aot-nmin2-pmin010-nobs-dthreads24-filled-long-deep-20260623T101219Z` | `MTP_DRAFT_THREADS=24` | 384/384 | 90.299 | 82.349 | Valid, below record. |
| 1 | `gemma4-q8-gpu1-mtp-n7-aot-nmin2-pmin010-nobs-dthreads32-repeat3-filled-long-deep-20260623T101219Z` | `MTP_DRAFT_THREADS=32` repeat | 384/384 | 90.228 | 82.281 | Valid repeat, below record. |
| 2 | `gemma4-q8-gpu2-mtp-n7-aot-nmin2-pmin010-nobs-dthreads48-filled-long-deep-20260623T101219Z` | `MTP_DRAFT_THREADS=48` | 384/384 | 89.675 | 81.734 | Valid, below record. |
| 3 | `gemma4-q8-gpu3-mtp-n7-aot-nmin2-pmin010-nobs-dthreads64-filled-long-deep-20260623T101219Z` | `MTP_DRAFT_THREADS=64` | 384/384 | 89.964 | 81.894 | Valid, below record. |

## Takeaways

- No draft-thread count beat the current `90.419 tok/s` record. No
  LocalMaxxing submission.
- `24` was the closest run in this sweep and had the best wall throughput, but
  the after-TTFT metric remains below the record and within normal noise.
- Thread counts above 32 degrade in this shape. Do not spend more record-chase
  slots above 32 unless the draft workload changes.
- Repeated `32` again landed below the record, reinforcing that `90.419` is near
  the upper edge of this config's distribution.

## Follow-Up

The closest non-winning interaction so far is `MTP_DRAFT_THREADS_BATCH=32`
(`90.312 tok/s`) under `p-min=0.10`. Next sweep should combine
`MTP_DRAFT_THREADS_BATCH=32` with the p-min neighborhood:

- `p-min=0.10` repeat + `MTP_DRAFT_THREADS_BATCH=32`;
- `p-min=0.11` + `MTP_DRAFT_THREADS_BATCH=32`;
- `p-min=0.12` + `MTP_DRAFT_THREADS_BATCH=32`;
- `p-min=0.13` + `MTP_DRAFT_THREADS_BATCH=32`.
