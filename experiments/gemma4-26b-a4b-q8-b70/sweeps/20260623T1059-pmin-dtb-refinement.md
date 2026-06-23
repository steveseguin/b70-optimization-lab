# 20260623T1059 P-Min and Draft-Batch-Thread Refinement

Goal: retune the narrow winning region around the current filled-long draft-MTP
record after broad runtime mechanism flags failed to improve it.

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
  `MTP_BACKEND_SAMPLING=0`, `MTP_DRAFT_THREADS=32`,
  `MTP_DRAFT_THREADS_BATCH=32`, `GGML_SYCL_DISABLE_OPT=0`, `FLASH_ATTN=off`,
  `POLL=50`, `BATCH_SIZE=512`, `UBATCH_SIZE=64`, `--parallel 1
  --cache-ram 0`;
- gate: `384/384` chat canary before benchmark;
- benchmark shape: actual `588` prompt tokens and `512` output tokens.

## Results

| GPU | Label | Change | Canary | tok/s after TTFT | tok/s wall | Decision |
| --- | --- | --- | --- | ---: | ---: | --- |
| 0 | `gemma4-q8-gpu0-mtp-n7-aot-nmin2-pmin0115-nobs-dthreads32-dtb32-filled-long-deep-20260623T1059Z` | `p-min=0.115` | 384/384 | 90.488 | 82.472 | Valid, below record. |
| 1 | `gemma4-q8-gpu1-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb32-repeat3-filled-long-deep-20260623T1059Z` | exact `p-min=0.12`, `dtb32` repeat | 384/384 | 90.006 | 82.066 | Valid repeat, below record. |
| 2 | `gemma4-q8-gpu2-mtp-n7-aot-nmin2-pmin0125-nobs-dthreads32-dtb32-filled-long-deep-20260623T1059Z` | `p-min=0.125` | 384/384 | 90.048 | 81.953 | Valid, below record. |
| 3 | `gemma4-q8-gpu3-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb40-filled-long-deep-20260623T1059Z` | `MTP_DRAFT_THREADS_BATCH=40` | 384/384 | 89.530 | 81.608 | Valid, below record. |

## Takeaways

- The earlier `91.046 tok/s` record is a real high-water mark but not easily
  reproducible by a simple repeat; recent repeats cluster closer to `90-90.5`.
- `p-min=0.115` was the best in this sweep but still below record.
- Raising draft batch threads above `32` hurt.

## Next Follow-Ups

- Test lower nearby draft batch thread counts (`28`, `36`) and nearby draft
  thread counts (`28`, `36`) before leaving this neighborhood.
- If none beat the record, consider pure record-repeat lanes or a new runtime
  build A/B rather than more small flag perturbations.
