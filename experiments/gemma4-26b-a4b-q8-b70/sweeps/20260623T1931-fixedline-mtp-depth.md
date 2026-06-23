# 2026-06-23T1931 Fixed-Line MTP Depth Diagnostic

Goal: check whether the current fresh-response Gemma 4 26B A4B Q8 draft-MTP
lane is acceptance-limited or implementation-overhead-limited by running a
highly predictable fresh prompt shape (`filled-fixed-line`) across deeper
`n_max` values.

This is **not** a promoted LocalMaxxing record attempt because it changes the
benchmark prompt shape from the current promoted `filled-long` identity. It is
still fresh-response valid for mechanism work:

- draft source is the Gemma MTP draft model, not n-gram/history speculation;
- `--cache-ram 0` and `--ctx-checkpoints 0` are retained;
- each lane passed the `384/384` chat canary;
- first-request throughput is available separately in the raw benchmark rows.

Reference fresh-response record for the promoted `filled-long` identity:

- `91.618942 tok/s` mean after TTFT;
- first request `91.251146 tok/s`;
- `384/384` chat canary;
- LocalMaxxing `cmqqsecuk01azqo018ahv0i1s`;
- artifact:
  `data/gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-repeat-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T150833Z/summary.json`.

Common identity:

- llama.cpp `c926ad098`, SYCL AOT BMG build;
- target: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: `mtp-gemma-4-26B-A4B-it.gguf`;
- one full model replica per B70;
- `LLAMA_MTP_DRAFT_FAST_TOPK=1`, `LLAMA_MTP_DRAFT_TOP_K=10`;
- backend draft sampling off;
- `MTP_N_MIN=2`, `MTP_P_MIN=0.12`;
- draft threads/batch `32/32`;
- `MTP_EXTRA_ARGS='--ctx-checkpoints 0'`;
- `BENCH_PROMPT_MODE=filled-fixed-line`, `PROMPT_TOKENS=512`,
  `MAX_TOKENS=512`;
- `CANARY_REPEATS=96`, `BENCH_REPEATS=8`;
- `GGML_SYCL_DISABLE_OPT=0`, `FLASH_ATTN=off`, `THREADS=16`.

## Results

| `n_max` | GPU | Canary | First request tok/s | Mean tok/s after TTFT | Wall tok/s | TTFT s | Decision |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 7 | 0 | 384/384 | 92.116983 | 92.043443 | 71.130707 | 1.635468 | valid diagnostic near-tie; do not promote across prompt shapes |
| 8 | 1 | 384/384 | 64.280098 | 64.195217 | 53.234439 | 1.642192 | valid loss |
| 12 | 2 | 384/384 | 74.705863 | 74.135651 | 59.858249 | 1.646926 | valid loss |
| 16 | 3 | 384/384 | 72.551379 | 73.414649 | 59.370171 | 1.649441 | valid loss |

Artifacts:

- `data/gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-fixedline-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-deep-20260623T193121Z/summary.json`
- `data/gemma4-q8-gpu1-mtp-n8-c926-fasttopk10-fixedline-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-deep-20260623T193121Z/summary.json`
- `data/gemma4-q8-gpu2-mtp-n12-c926-fasttopk10-fixedline-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-deep-20260623T193121Z/summary.json`
- `data/gemma4-q8-gpu3-mtp-n16-c926-fasttopk10-fixedline-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-deep-20260623T193121Z/summary.json`

## Acceptance And Mechanism Notes

The `n=7` lane has very high acceptance on the benchmark requests:

- accepted about `446/452-453` drafted tokens per 512-token benchmark request;
- mean acceptance length about `7.86`;
- per-position acceptance around `0.985-1.000` through most positions.

Increasing depth did not help:

- `n=8` accepted all benchmark draft tokens (`454/454`, mean acceptance length
  `8.96`) but collapsed to `64.20 tok/s`;
- `n=12` reached mean acceptance length about `11.36-11.88` but only
  `74.14 tok/s`;
- `n=16` reached mean acceptance length about `12.17-12.46` but only
  `73.41 tok/s`.

This strongly reinforces the prior profile conclusion: the current llama.cpp
fresh-response MTP lane is not acceptance-limited. Deeper MTP chunks add enough
draft/verifier overhead that they lose even on a highly predictable fresh
continuation. The practical next work is therefore:

1. vLLM/XPU int8-per-channel comparison once the official HF snapshot finishes
   downloading;
2. source/kernel work that reduces target verification or draft decode cost per
   accepted chunk;
3. avoid further small `n`, `p-min`, draft-thread, VMM, ubatch, or poll sweeps
   under this same llama.cpp MTP identity unless a source change first moves
   the bottleneck.

No LocalMaxxing submission was made.
