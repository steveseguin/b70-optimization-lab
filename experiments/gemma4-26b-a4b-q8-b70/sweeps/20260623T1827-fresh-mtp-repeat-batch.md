# 2026-06-23 18:27Z: Fresh MTP Record Repeat Batch

Goal: re-check the current valid fresh-response Gemma 4 26B A4B Q8 record
lane after the n-gram/history validity correction, and test whether the
VMM/ubatch wall-speed lane or a tiny `p-min` relaxation can beat the promoted
draft-MTP fast-top-k result.

Current valid fresh-response record for this shape:

- `91.61894213332073 tok/s` mean after TTFT;
- first request `91.25114630080908 tok/s`;
- `384/384` chat canary;
- LocalMaxxing `cmqqsecuk01azqo018ahv0i1s`;
- run:
  `data/gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-repeat-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T150833Z/summary.json`.

Fresh-response validity notes:

- These are draft-model MTP runs, not draftless n-gram/history runs.
- `--ctx-checkpoints 0` and `--cache-ram 0` are used; benchmark rows report
  `cached_tokens=None` in the OpenAI response artifact.
- Report first request and repeat mean separately. Do not use warmed n-gram
  artifacts as comparison rows for this table.

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

## Results

| Variant | Gate | First request tok/s | Mean tok/s after TTFT | Wall tok/s | TTFT ms | Delta vs record | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| exact repeat A, `p-min=0.12` | 384/384 | 90.814844 | 90.879363 | 70.769855 | 1600.953 | -0.739579 | valid loss |
| exact repeat B, `p-min=0.12` | 384/384 | 90.807369 | 90.953619 | 70.832597 | 1599.110 | -0.665323 | valid loss |
| `VMM=0`, `UBATCH_SIZE=512`, `p-min=0.12` | 384/384 | 91.113426 | 91.400260 | 82.175502 | 630.930 | -0.218682 | valid loss; best wall/TTFT in batch |
| `p-min=0.118` | 384/384 | 91.127009 | 90.966209 | 70.844900 | 1598.621 | -0.652733 | valid loss |

Artifacts:

- `data/gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-fresh-repeatA-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T182732Z/summary.json`
- `data/gemma4-q8-gpu1-mtp-n7-c926-fasttopk10-fresh-repeatB-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T182732Z/summary.json`
- `data/gemma4-q8-gpu2-mtp-n7-c926-fasttopk10-vmm0-ub512-fresh-repeat-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T182732Z/summary.json`
- `data/gemma4-q8-gpu3-mtp-n7-c926-fasttopk10-pmin0118-fresh-ctxcp0-nmin2-nobs-dthreads32-dtb32-filled-long-deep-20260623T182732Z/summary.json`

Decision:

- No LocalMaxxing submission. All four candidates are valid fresh-response
  losses against the promoted `91.618942` tok/s record.
- The `VMM=0 + UBATCH_SIZE=512` lane remains useful for wall throughput and
  TTFT-sensitive applications (`~82.18` wall tok/s, `~631 ms` TTFT), but it has
  not beaten the after-TTFT decode metric.
- Exact repeats came in around `90.9-91.0 tok/s`, so future flag-only work
  should not assume that the `91.62` record is easy to reproduce. Favor changes
  that can plausibly reduce draft overhead or increase accepted tokens per
  target verification rather than small `p-min` tweaks alone.
