# 20260623T1050 Sampler, KV, Priority, and CPU-Mask Sweep

Goal: test remaining supported llama.cpp mechanism flags under the current
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
  `MTP_P_MIN=0.12`, `MTP_BACKEND_SAMPLING=0`, `MTP_DRAFT_THREADS=32`,
  `MTP_DRAFT_THREADS_BATCH=32`, `GGML_SYCL_DISABLE_OPT=0`, `FLASH_ATTN=off`,
  `POLL=50`, `BATCH_SIZE=512`, `UBATCH_SIZE=64`, `--parallel 1
  --cache-ram 0`;
- gate: `384/384` chat canary before benchmark;
- benchmark shape: actual `588` prompt tokens and `512` output tokens.

## Results

| GPU | Label | Change | Canary | tok/s after TTFT | tok/s wall | Decision |
| --- | --- | --- | --- | ---: | ---: | --- |
| 0 | `gemma4-q8-gpu0-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb32-nokvunified-filled-long-deep-20260623T1050Z` | `--no-kv-unified` | 384/384 | 89.991 | 82.059 | Valid, below record. |
| 1 | `gemma4-q8-gpu1-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb32-greedy-filled-long-deep-20260623T1050Z` | `--samplers greedy` | 384/384 | 88.652 | 80.790 | Valid, below record; changed benchmark text formatting and hurt speed. |
| 2 | `gemma4-q8-gpu2-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb32-prio1-filled-long-deep-20260623T1050Z` | `--prio 1 --prio-batch 1 --spec-draft-prio 1 --spec-draft-prio-batch 1` | 384/384 | 89.719 | 81.765 | Valid, below record. |
| 3 | `gemma4-q8-gpu3-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb32-cpumask-split-filled-long-deep-20260623T1050Z` | target/draft CPU mask split with supported draft batch mask flags | 384/384 | 89.730 | 81.738 | Valid, below record. |

## Takeaways

- `--no-kv-unified` does not help the single-slot `--parallel 1` case.
- Greedy-only sampler removes sampler-chain complexity but is slower here and
  changes output formatting. Keep the default sampler chain for promoted runs.
- Scheduler priority and CPU mask split did not help; they likely add CPU
  scheduling friction instead of removing the target/draft bottleneck.

## Next Follow-Ups

The mechanism sweep space is mostly exhausted. Next cheap record-chasing work
should retune the narrow winning neighborhood rather than add unrelated flags:

- repeat the exact `p-min=0.12 + dtb32` current record identity to measure
  variance and possibly break the record;
- test `p-min=0.115` and `p-min=0.125` with the same identity;
- test nearby draft batch thread counts such as `24` or `40`.
