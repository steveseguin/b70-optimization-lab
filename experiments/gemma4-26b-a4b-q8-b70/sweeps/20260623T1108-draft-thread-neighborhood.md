# 20260623T1108 Draft Thread Neighborhood

Goal: test nearby draft thread and draft batch thread counts around the current
filled-long draft-MTP record identity.

Record to beat:

- label:
  `gemma4-q8-gpu2-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T101814Z`;
- speed: `91.04565350124257 tok/s` after TTFT, `82.9656977099596 tok/s`
  warmed wall;
- quality: `384/384` chat canary.

Common identity unless listed in `Change`:

- runtime: llama.cpp `dec5ca557`, SYCL/Level Zero, AOT BMG build
  `/home/steve/src/llama.cpp/build-sycl-b70-aot-bmg-g31/bin/llama-server`;
- model: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: `mtp-gemma-4-26B-A4B-it.gguf`;
- flags: `BENCH_PROMPT_MODE=filled-long`, `MTP_N_MAX=7`, `MTP_N_MIN=2`,
  `MTP_P_MIN=0.12`, `MTP_BACKEND_SAMPLING=0`, `GGML_SYCL_DISABLE_OPT=0`,
  `FLASH_ATTN=off`, `POLL=50`, `BATCH_SIZE=512`, `UBATCH_SIZE=64`,
  `--parallel 1 --cache-ram 0`;
- gate: `384/384` chat canary before benchmark;
- benchmark shape: actual `588` prompt tokens and `512` output tokens.

## Results

| GPU | Label | Change | Canary | tok/s after TTFT | tok/s wall | Decision |
| --- | --- | --- | --- | ---: | ---: | --- |
| 0 | `gemma4-q8-gpu0-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb28-filled-long-deep-20260623T1108Z` | `MTP_DRAFT_THREADS=32`, `MTP_DRAFT_THREADS_BATCH=28` | 384/384 | 90.596 | 82.616 | Valid, below record; closest in this sweep. |
| 1 | `gemma4-q8-gpu1-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb36-filled-long-deep-20260623T1108Z` | `MTP_DRAFT_THREADS=32`, `MTP_DRAFT_THREADS_BATCH=36` | 384/384 | 90.109 | 82.177 | Valid, below record. |
| 2 | `gemma4-q8-gpu2-mtp-n7-aot-nmin2-pmin012-nobs-dthreads28-dtb32-filled-long-deep-20260623T1108Z` | `MTP_DRAFT_THREADS=28`, `MTP_DRAFT_THREADS_BATCH=32` | 384/384 | 90.432 | 82.454 | Valid, below record. |
| 3 | `gemma4-q8-gpu3-mtp-n7-aot-nmin2-pmin012-nobs-dthreads36-dtb32-filled-long-deep-20260623T1108Z` | `MTP_DRAFT_THREADS=36`, `MTP_DRAFT_THREADS_BATCH=32` | 384/384 | 89.965 | 81.827 | Valid, below record. |

## Takeaways

- Lowering draft batch threads from `32` to `28` was the only near-neutral move,
  but it still did not beat the `91.046 tok/s` record.
- Draft worker thread counts above/below `32` remain losses, consistent with
  the broader `24/32/48/64` sweep.

## Next Follow-Ups

Only test interactions among near-neutral results:

- `dtb28 + FLASH_ATTN=on + draft V q8_0`;
- `dtb28 + p-min=0.115`;
- `dtb28 + POLL=100`;
- exact `dtb28` repeat on a different GPU to estimate variance.
