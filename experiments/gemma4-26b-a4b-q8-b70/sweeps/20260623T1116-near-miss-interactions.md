# 20260623T1116 Near-Miss Interaction Sweep

Goal: combine the best near-neutral moves from recent sweeps to see whether
small interactions can beat the current filled-long draft-MTP record.

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
  `GGML_SYCL_DISABLE_OPT=0`, `BATCH_SIZE=512`, `UBATCH_SIZE=64`,
  `--parallel 1 --cache-ram 0`;
- gate: `384/384` chat canary before benchmark;
- benchmark shape: actual `588` prompt tokens and `512` output tokens.

## Results

| GPU | Label | Change | Canary | tok/s after TTFT | tok/s wall | Decision |
| --- | --- | --- | --- | ---: | ---: | --- |
| 0 | `gemma4-q8-gpu0-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb28-faon-dv-q8-filled-long-deep-20260623T1116Z` | `dtb28`, `FLASH_ATTN=on`, draft `V=q8_0` | 384/384 | 90.427 | 84.036 | Valid, below record; lower TTFT / better wall, but decode below record. |
| 1 | `gemma4-q8-gpu1-mtp-n7-aot-nmin2-pmin0115-nobs-dthreads32-dtb28-filled-long-deep-20260623T1116Z` | `dtb28`, `p-min=0.115` | 384/384 | 89.950 | 82.066 | Valid, below record. |
| 2 | `gemma4-q8-gpu2-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb28-repeat-filled-long-deep-20260623T1116Z` | `dtb28` repeat | 384/384 | 90.228 | 82.116 | Valid, below record. |
| 3 | `gemma4-q8-gpu3-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb28-poll100-filled-long-deep-20260623T1116Z` | `dtb28`, `POLL=100` | 384/384 | 90.081 | 82.122 | Valid, below record. |

## Takeaways

- Combining the near-misses did not stack into a new decode record.
- `FLASH_ATTN=on + draft V q8_0` consistently improves TTFT/wall but remains
  below the after-TTFT decode record.
- `dtb28` is near-neutral but not better than the original `dtb32` high-water
  mark.

## Next Follow-Ups

- Run exact-record repeats across all GPUs to estimate whether `91.046 tok/s`
  is repeatable or a high-water outlier.
- If repeats do not beat the record, the next meaningful work is a new
  llama.cpp build A/B or a different runtime lane, not more small flag
  combinations.
