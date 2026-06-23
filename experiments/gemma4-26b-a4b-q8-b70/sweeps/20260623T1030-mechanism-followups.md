# 20260623T1030 Mechanism Follow-Ups Under the DTB32 Record Identity

Goal: test mechanism-level follow-ups under the current filled-long draft-MTP
record identity, not retune the confidence gate again. The record to beat was:

- label:
  `gemma4-q8-gpu2-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T101814Z`;
- speed: `91.04565350124257 tok/s` after TTFT, `82.9656977099596 tok/s`
  warmed wall;
- quality: `384/384` chat canary;
- LocalMaxxing ID: `cmqqi1p2c016jqo01vndau1y9`.

Common identity unless listed in `Change`:

- runtime: llama.cpp `dec5ca557`, SYCL/Level Zero, AOT BMG build
  `/home/steve/src/llama.cpp/build-sycl-b70-aot-bmg-g31/bin/llama-server`;
- model: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: `mtp-gemma-4-26B-A4B-it.gguf`;
- flags: `BENCH_PROMPT_MODE=filled-long`, `MTP_N_MAX=7`, `MTP_N_MIN=2`,
  `MTP_P_MIN=0.12`, `MTP_BACKEND_SAMPLING=0`, `MTP_DRAFT_THREADS=32`,
  `MTP_DRAFT_THREADS_BATCH=32`, `GGML_SYCL_DISABLE_OPT=0`, `POLL=50`,
  `BATCH_SIZE=512`, `UBATCH_SIZE=64`, `--parallel 1 --cache-ram 0`;
- gate: `384/384` chat canary before benchmark;
- benchmark shape: actual `588` prompt tokens and `512` output tokens.

## Results

| GPU | Label | Change | Canary | tok/s after TTFT | tok/s wall | Decision |
| --- | --- | --- | --- | ---: | ---: | --- |
| 0 | `gemma4-q8-gpu0-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb32-faon-dv-q8-filled-long-deep-20260623T103024Z` | `FLASH_ATTN=on`, draft `V` cache `q8_0`, draft `K` cache `f16` | 384/384 | 90.613 | 84.187 | Valid real q8 draft-cache run, below record. |
| 1 | `gemma4-q8-gpu1-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb32-faon-dkv-q8-filled-long-deep-20260623T103024Z` | `FLASH_ATTN=on`, draft `K/V` cache `q8_0` | 384/384 | 89.950 | 83.591 | Valid real q8 draft-cache run, below record. |
| 2 | `gemma4-q8-gpu2-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb32-poll100-filled-long-deep-20260623T103024Z` | `POLL=100` | 384/384 | 90.586 | 82.593 | Valid, below record; higher poll increases TTFT and does not improve decode. |
| 3 | `gemma4-q8-gpu3-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb32-cpurange-split-filled-long-deep-20260623T103024Z` | attempted target/draft CPU-affinity split | n/a | n/a | n/a | Launcher failed: this build rejects `--spec-draft-cpu-range-batch`. |

## Validity Notes

- These are not repeats of the earlier invalid draft-q8 cache tests. The earlier
  `FLASH_ATTN=off` attempts logged `V cache quantization requires flash_attn`
  and fell back. These runs used `FLASH_ATTN=on`, and server logs show:
  - draft `V` run: `cache_k=f16, cache_v=q8_0`;
  - draft `K/V` run: `cache_k=q8_0, cache_v=q8_0`.
- The q8 draft-cache variants improved wall throughput slightly because TTFT is
  lower, but the promoted comparison metric is after-TTFT decode. Both are below
  the `91.046 tok/s` record.
- The CPU-affinity idea may still be worth testing with only the supported flags
  (`--spec-draft-cpu-range` and no draft batch range), but this exact flag set is
  not supported by llama.cpp `dec5ca557`.

## Next Follow-Ups

Use the current `p-min=0.12 + draft-threads-batch=32` record identity for the
next batch:

- `MTP_DRAFT_POLL=0`;
- Q8_0 main model control with the same MTP identity;
- supported CPU-affinity split without `--spec-draft-cpu-range-batch`;
- `GGML_SYCL_ENABLE_VMM=0` as a lower-priority runtime diagnostic.
