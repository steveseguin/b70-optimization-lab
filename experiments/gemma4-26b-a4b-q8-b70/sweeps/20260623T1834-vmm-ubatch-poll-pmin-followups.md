# 2026-06-23 18:34Z: VMM/UBatch Poll And P-Min Follow-Ups

Goal: continue valid fresh-response optimization after the n-gram/history
validity correction. This batch tested the best recent wall/TTFT lane
(`GGML_SYCL_ENABLE_VMM=0 + UBATCH_SIZE=512`) with `POLL=100` and nearby
`p-min` values.

Current valid fresh-response record for comparison:

- `91.61894213332073 tok/s` mean after TTFT;
- first request `91.25114630080908 tok/s`;
- `384/384` chat canary;
- LocalMaxxing `cmqqsecuk01azqo018ahv0i1s`;
- run:
  `data/gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-repeat-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T150833Z/summary.json`.

Common identity:

- llama.cpp `c926ad098`, SYCL AOT BMG build;
- target model: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft model: `mtp-gemma-4-26B-A4B-it.gguf`;
- one full model replica per B70;
- `MTP_N_MAX=7`, `MTP_N_MIN=2`, backend sampling off;
- `LLAMA_MTP_DRAFT_FAST_TOPK=1`, `LLAMA_MTP_DRAFT_TOP_K=10`;
- `MTP_DRAFT_THREADS=32`, `MTP_DRAFT_THREADS_BATCH=32`;
- `MTP_EXTRA_ARGS='--ctx-checkpoints 0'`;
- `BENCH_PROMPT_MODE=filled-long`, `PROMPT_TOKENS=512`, `MAX_TOKENS=512`;
- `CANARY_REPEATS=96`, `BENCH_REPEATS=8`;
- `GGML_SYCL_DISABLE_OPT=0`, `FLASH_ATTN=off`, `THREADS=16`.

Fresh-response validity:

- draft-model MTP only; no draftless n-gram/history acceleration;
- context checkpoints disabled and `--cache-ram 0`;
- first request reported separately; repeat mean is not warmed by prior target
  continuations.

## Results

| Variant | Gate | First request tok/s | Mean tok/s after TTFT | Wall tok/s | TTFT ms | Delta vs record | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `VMM=0`, `UBATCH_SIZE=512`, `POLL=100`, `p-min=0.12` | 384/384 | 92.238938 | 91.520413 | 82.196523 | 636.134 | -0.098530 | valid near-loss; best wall/TTFT in batch |
| `VMM=0`, `UBATCH_SIZE=512`, `p-min=0.115` | 384/384 | 90.787104 | 90.917528 | 81.655753 | 640.952 | -0.701414 | valid loss |
| `VMM=0`, `UBATCH_SIZE=512`, `p-min=0.125` | 384/384 | 90.942986 | 91.032057 | 81.813500 | 636.379 | -0.586886 | valid loss |
| `CTX_SIZE=4096`, `VMM=0`, `UBATCH_SIZE=512`, `POLL=100`, `p-min=0.12` | 384/384 | 90.993522 | 90.980384 | 81.792267 | 634.254 | -0.638558 | valid small-context loss |

Artifacts:

- `data/gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-vmm0-ub512-poll100-fresh-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T183453Z/summary.json`
- `data/gemma4-q8-gpu1-mtp-n7-c926-fasttopk10-vmm0-ub512-pmin0115-fresh-ctxcp0-nmin2-nobs-dthreads32-dtb32-filled-long-deep-20260623T183453Z/summary.json`
- `data/gemma4-q8-gpu2-mtp-n7-c926-fasttopk10-vmm0-ub512-pmin0125-fresh-ctxcp0-nmin2-nobs-dthreads32-dtb32-filled-long-deep-20260623T183453Z/summary.json`
- `data/gemma4-q8-gpu3-mtp-n7-c926-fasttopk10-ctx4096-vmm0-ub512-poll100-fresh-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T183453Z/summary.json`

Decision:

- No LocalMaxxing submission. All four lanes passed quality but missed the
  `91.618942` mean-after-TTFT record.
- The `VMM=0 + UBATCH_SIZE=512 + POLL=100` lane is the closest valid loss
  since the record (`91.520413`, only `0.0985 tok/s` below) and had a fast
  first request (`92.238938`). It is a strong wall/TTFT lane, not a promoted
  after-TTFT decode record.
- The p-min neighborhood under VMM/UB512 is exhausted for this identity:
  `0.115`, `0.12`, and `0.125` all lost. Further gains probably require a
  source-level draft-loop change or a different runtime, not another small flag
  sweep.
