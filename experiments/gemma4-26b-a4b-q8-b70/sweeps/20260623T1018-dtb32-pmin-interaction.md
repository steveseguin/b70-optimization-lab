# 20260623T1018 Draft-Threads-Batch / P-Min Interaction Sweep

Goal: combine the closest non-winning runtime interaction,
`MTP_DRAFT_THREADS_BATCH=32`, with the useful `p-min` neighborhood around the
current filled-long MTP identity.

Common identity:

- runtime: llama.cpp `dec5ca557`, SYCL/Level Zero, AOT BMG build
  `/home/steve/src/llama.cpp/build-sycl-b70-aot-bmg-g31/bin/llama-server`;
- model: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: `mtp-gemma-4-26B-A4B-it.gguf`;
- baseline flags: `BENCH_PROMPT_MODE=filled-long`, `MTP_N_MAX=7`,
  `MTP_N_MIN=2`, `MTP_BACKEND_SAMPLING=0`, `MTP_DRAFT_THREADS=32`,
  `MTP_DRAFT_THREADS_BATCH=32`, `GGML_SYCL_DISABLE_OPT=0`,
  `FLASH_ATTN=off`, `POLL=50`, `BATCH_SIZE=512`, `UBATCH_SIZE=64`,
  `--parallel 1 --cache-ram 0`;
- quality gate: `384/384` chat canary before benchmark;
- benchmark shape: actual `588` prompt tokens and `512` output tokens.

Previous record to beat:

- `gemma4-q8-gpu3-mtp-n7-aot-nmin2-pmin010-nobs-dthreads32-filled-long-deep-20260623T094131Z`;
- `90.41948035379636 tok/s` after TTFT, `82.3415769722187 tok/s` wall;
- LocalMaxxing approved as `cmqqgn3cm0163qo010optg91u`.

## Results

| GPU | Label | Change | Canary | tok/s after TTFT | tok/s wall | Decision |
| --- | --- | --- | --- | ---: | ---: | --- |
| 0 | `gemma4-q8-gpu0-mtp-n7-aot-nmin2-pmin010-nobs-dthreads32-dtb32-repeat2-filled-long-deep-20260623T101814Z` | `p-min=0.10`, `MTP_DRAFT_THREADS_BATCH=32` repeat | n/a | n/a | n/a | Launch/readiness stall on GPU0 during model load; killed and kept as a failed control artifact. |
| 1 | `gemma4-q8-gpu1-mtp-n7-aot-nmin2-pmin011-nobs-dthreads32-dtb32-filled-long-deep-20260623T101814Z` | `p-min=0.11`, `MTP_DRAFT_THREADS_BATCH=32` | 384/384 | 89.634 | 81.469 | Valid, below record. |
| 2 | `gemma4-q8-gpu2-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T101814Z` | `p-min=0.12`, `MTP_DRAFT_THREADS_BATCH=32` | 384/384 | **91.046** | **82.966** | New valid record; submitted to LocalMaxxing. |
| 3 | `gemma4-q8-gpu3-mtp-n7-aot-nmin2-pmin013-nobs-dthreads32-dtb32-filled-long-deep-20260623T101814Z` | `p-min=0.13`, `MTP_DRAFT_THREADS_BATCH=32` | 384/384 | 90.243 | 82.254 | Valid, below new record. |

## Promotion

- LocalMaxxing ID: `cmqqi1p2c016jqo01vndau1y9`;
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb32-filledlong512-20260623.queue.json`;
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb32-filledlong512-20260623.submit.log`.

## Takeaways

- The useful interaction is real: `MTP_DRAFT_THREADS_BATCH=32` plus
  `p-min=0.12` improved the filled-long after-TTFT record from `90.419` to
  `91.046 tok/s` with the same 384-row chat gate.
- `p-min=0.13` with the same interaction regressed to `90.243`, so keep
  `0.12` as the promoted confidence threshold for this interaction.
- The old `p-min=0.10` + `dtb32` control previously measured `90.312`; this
  repeat stalled during startup on GPU0 and was not used as a benchmark.
- Future gains below about `0.3 tok/s` still need repeat confirmation because
  the record neighborhood is noisy.

## Follow-Up

Next record-chasing sweep should test mechanisms not already exhausted:

- true `FLASH_ATTN=on` plus draft `V` cache `q8_0`;
- true `FLASH_ATTN=on` plus draft `K/V` cache `q8_0`;
- `POLL=100` under the new `p-min=0.12 + dtb32` identity;
- CPU affinity split between target and draft threads under the new identity.
