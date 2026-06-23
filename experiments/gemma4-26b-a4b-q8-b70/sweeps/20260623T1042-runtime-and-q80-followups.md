# 20260623T1042 Runtime and Q8_0 Follow-Ups

Goal: continue mechanism-level tests under the current filled-long draft-MTP
record identity after the FA-on draft-cache/POLL=100 sweep did not beat the
record.

Record to beat:

- label:
  `gemma4-q8-gpu2-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T101814Z`;
- speed: `91.04565350124257 tok/s` after TTFT, `82.9656977099596 tok/s`
  warmed wall;
- quality: `384/384` chat canary;
- LocalMaxxing ID: `cmqqi1p2c016jqo01vndau1y9`.

Common identity unless listed in `Change`:

- runtime: llama.cpp `dec5ca557`, SYCL/Level Zero, AOT BMG build
  `/home/steve/src/llama.cpp/build-sycl-b70-aot-bmg-g31/bin/llama-server`;
- main model: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
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
| 0 | `gemma4-q8-gpu0-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb32-draftpoll0-filled-long-deep-20260623T1042Z` | `--spec-draft-poll 0` | 384/384 | 90.163 | 82.154 | Valid, below record. |
| 1 | `gemma4-q80-gpu1-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T1042Z` | main model `gemma-4-26B-A4B-it-Q8_0.gguf` | 384/384 | 89.987 | 81.776 | Valid Q8_0 control, below UD-Q8_K_XL record. |
| 2 | `gemma4-q8-gpu2-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb32-cpurange-supported-filled-long-deep-20260623T1042Z` | supported CPU-range split without unsupported draft batch range | 384/384 | 89.946 | 81.944 | Valid, below record. |
| 3 | `gemma4-q8-gpu3-mtp-n7-aot-nmin2-pmin012-nobs-dthreads32-dtb32-vmm0-filled-long-deep-20260623T1042Z` | `GGML_SYCL_ENABLE_VMM=0` | 384/384 | 90.395 | 82.301 | Valid, below record; best in this sweep but still short. |

## Takeaways

- `MTP_DRAFT_POLL=0` is not a useful interaction under the final n7/pmin0.12
  identity.
- Q8_0 main weights are valid but slower than UD-Q8_K_XL on the promoted
  filled-long shape. Keep Q8_0 as a compatibility/control lane, not a promoted
  speed lane.
- CPU range separation did not recover enough scheduling overhead to help. The
  exact unsupported `--spec-draft-cpu-range-batch` path remains documented in
  the previous sweep; this run used only supported range flags.
- Disabling SYCL VMM was neutral-to-slightly-negative. It did not produce a new
  record.

## Next Follow-Ups

The next batch should test only new mechanisms:

- `--no-kv-unified`;
- `--samplers greedy`;
- scheduler priority flags without CPU pinning;
- CPU mask split with the supported draft batch mask flags.
