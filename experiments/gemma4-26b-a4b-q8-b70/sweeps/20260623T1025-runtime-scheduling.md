# 20260623T1025 Runtime Scheduling Sweep

Goal: continue from the current valid filled-long MTP record
(`90.419 tok/s`, `n=7`, `n-min=2`, `p-min=0.10`, backend sampling off,
draft threads 32) and test whether nearby runtime scheduling knobs move
single-session decode.

Common identity:

- runtime: llama.cpp `dec5ca557`, SYCL/Level Zero, AOT BMG build
  `/home/steve/src/llama.cpp/build-sycl-b70-aot-bmg-g31/bin/llama-server`;
- model: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: `mtp-gemma-4-26B-A4B-it.gguf`;
- baseline flags: `BENCH_PROMPT_MODE=filled-long`, `MTP_N_MAX=7`,
  `MTP_N_MIN=2`, `MTP_P_MIN=0.10`, `MTP_BACKEND_SAMPLING=0`,
  `MTP_DRAFT_THREADS=32`, `GGML_SYCL_DISABLE_OPT=0`, `FLASH_ATTN=off`,
  `POLL=50`, `BATCH_SIZE=512`, `UBATCH_SIZE=64`,
  `--parallel 1 --cache-ram 0`;
- quality gate: `384/384` chat canary before benchmark;
- benchmark shape: actual `588` prompt tokens and `512` output tokens.

## Results

| GPU | Label | Change | Canary | tok/s after TTFT | tok/s wall | Decision |
| --- | --- | --- | --- | ---: | ---: | --- |
| 0 | `gemma4-q8-gpu0-mtp-n7-aot-nmin2-pmin010-nobs-dthreads32-mainthreads32-filled-long-deep-20260623T102500Z` | main `THREADS=32` | 384/384 | 90.120 | 82.190 | Valid, below record. More CPU main threads do not help this single-session decode path. |
| 1 | `gemma4-q8-gpu1-mtp-n7-aot-nmin2-pmin010-nobs-dthreads32-dtb32-filled-long-deep-20260623T102500Z` | `MTP_DRAFT_THREADS_BATCH=32` | 384/384 | 90.312 | 82.344 | Valid and closest in this sweep, but still below `90.419`. Keep as a possible interaction term, not a promotion. |
| 2 | `gemma4-q8-gpu2-mtp-n7-aot-nmin2-pmin010-nobs-dthreads32-poll75-filled-long-deep-20260623T102500Z` | `POLL=75` | 384/384 | 90.015 | 81.898 | Valid, below record. |
| 3 | `gemma4-q8-gpu3-mtp-n7-aot-nmin2-pmin010-nobs-dthreads32-faon-filled-long-deep-20260623T102500Z` | `FLASH_ATTN=on` | 384/384 | 90.083 | 83.685 | Valid, below record. FA-on improves wall via lower TTFT but not decode-after-TTFT. |

## Takeaways

- None of the four scheduling/runtime knobs beat the current `90.419 tok/s`
  record. No LocalMaxxing submission.
- `MTP_DRAFT_THREADS_BATCH=32` is the closest neutral result. It may be worth
  combining with a future `p-min` sweep if there is a spare slot, but it is not
  enough alone.
- `FLASH_ATTN=on` is slightly slower on after-TTFT decode in this identity, but
  remains necessary for a real draft `q8_0` V-cache or K/V-cache retest because
  llama.cpp rejects V-cache quantization without flash attention.
- The record margin is small. Treat single-run gains below about `0.3 tok/s` as
  weak until repeated or explained by a clear mechanism.

## Follow-Up

Next four-way sweep should refine the current strongest lever, draft confidence
threshold, while holding `MTP_DRAFT_THREADS=32`:

- repeat `p-min=0.10` as a control;
- `p-min=0.11`;
- `p-min=0.12`;
- `p-min=0.13`.

If none improves, sweep draft thread count around the winner (`24`, `32`
repeat, `48`, `64`) and then run the Q8_0 main-model control under the promoted
MTP identity.
