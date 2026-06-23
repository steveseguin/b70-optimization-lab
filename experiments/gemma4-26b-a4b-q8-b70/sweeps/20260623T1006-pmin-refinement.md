# 20260623T1006 P-Min Refinement Sweep

Goal: refine the current valid filled-long MTP record around the `p-min=0.10`
winner while holding the other winning knobs fixed.

Common identity:

- runtime: llama.cpp `dec5ca557`, SYCL/Level Zero, AOT BMG build
  `/home/steve/src/llama.cpp/build-sycl-b70-aot-bmg-g31/bin/llama-server`;
- model: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: `mtp-gemma-4-26B-A4B-it.gguf`;
- baseline flags: `BENCH_PROMPT_MODE=filled-long`, `MTP_N_MAX=7`,
  `MTP_N_MIN=2`, `MTP_BACKEND_SAMPLING=0`, `MTP_DRAFT_THREADS=32`,
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
| 0 | `gemma4-q8-gpu0-mtp-n7-aot-nmin2-pmin010-nobs-dthreads32-repeat2-filled-long-deep-20260623T100620Z` | repeat `p-min=0.10` | 384/384 | 90.201 | 82.095 | Valid repeat, below record. |
| 1 | `gemma4-q8-gpu1-mtp-n7-aot-nmin2-pmin011-nobs-dthreads32-filled-long-deep-20260623T100620Z` | `p-min=0.11` | 384/384 | 89.549 | 81.650 | Valid, below record. |
| 2 | `gemma4-q8-gpu2-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-filled-long-deep-20260623T100620Z` | `p-min=0.12` | 384/384 | 90.080 | 82.057 | Valid, below record. |
| 3 | `gemma4-q8-gpu3-mtp-n7-aot-nmin2-pmin013-nobs-dthreads32-filled-long-deep-20260623T100620Z` | `p-min=0.13` | 384/384 | 90.332 | 82.134 | Valid and closest in this sweep, but still below `90.419`. |

## Takeaways

- No `p-min` value in `0.10..0.13` beat the current record. No LocalMaxxing
  submission.
- `p-min=0.13` was closest but the delta is still negative (`-0.087 tok/s`)
  against the record. This is within normal run-to-run noise and does not
  justify changing the promoted identity.
- The repeated `p-min=0.10` result (`90.201`) reinforces that the `90.419`
  record is real but near the high end of this config's noise band.
- The `p-min` knob is likely exhausted around the current optimum. Move to
  draft-thread count or a different model/runtime identity.

## Follow-Up

Next four-way sweep:

- `MTP_DRAFT_THREADS=24`;
- `MTP_DRAFT_THREADS=32` repeat;
- `MTP_DRAFT_THREADS=48`;
- `MTP_DRAFT_THREADS=64`.

If none beats the record, run the Q8_0 main-model control and a true FA-on
draft-cache retest only if there is a clear reason to accept the lower FA-on
decode baseline.
