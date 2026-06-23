# 20260623T1124 Exact Record Repeats

Goal: repeat the current filled-long draft-MTP record identity across all four
B70s to estimate whether the `91.046 tok/s` high-water mark is repeatable.

Repeated identity:

- `BENCH_PROMPT_MODE=filled-long`;
- `MTP_N_MAX=7`, `MTP_N_MIN=2`, `MTP_P_MIN=0.12`;
- `MTP_BACKEND_SAMPLING=0`;
- `MTP_DRAFT_THREADS=32`, `MTP_DRAFT_THREADS_BATCH=32`;
- llama.cpp `dec5ca557`, AOT BMG build;
- main `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft `mtp-gemma-4-26B-A4B-it.gguf`;
- `GGML_SYCL_DISABLE_OPT=0`, `FLASH_ATTN=off`, `POLL=50`,
  `BATCH_SIZE=512`, `UBATCH_SIZE=64`, `--parallel 1 --cache-ram 0`;
- `384/384` chat canary before benchmark.

Record to beat:

- label:
  `gemma4-q8-gpu2-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T101814Z`;
- speed: `91.04565350124257 tok/s` after TTFT, `82.9656977099596 tok/s`
  warmed wall.

## Results

| GPU | Label | Canary | tok/s after TTFT | tok/s wall | Decision |
| --- | --- | --- | ---: | ---: | --- |
| 0 | `gemma4-q8-gpu0-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb32-repeat4-filled-long-deep-20260623T1124Z` | 384/384 | 90.414 | 82.401 | Valid, below record. |
| 1 | `gemma4-q8-gpu1-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb32-repeat4-filled-long-deep-20260623T1124Z` | 384/384 | 89.873 | 81.788 | Valid, below record. |
| 2 | `gemma4-q8-gpu2-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb32-repeat4-filled-long-deep-20260623T1124Z` | 384/384 | 90.160 | 82.126 | Valid, below record. |
| 3 | `gemma4-q8-gpu3-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb32-repeat4-filled-long-deep-20260623T1124Z` | 384/384 | 90.084 | 82.060 | Valid, below record. |

## Takeaways

- The current record remains valid, but recent exact repeats cluster around
  `89.9-90.4 tok/s`. Treat `91.046 tok/s` as the high-water mark for this
  build/config rather than an easily repeated steady state.
- Small flag perturbations have not beaten the high-water mark. The next
  meaningful direction is a new build/runtime A/B or a materially different
  runtime lane.
