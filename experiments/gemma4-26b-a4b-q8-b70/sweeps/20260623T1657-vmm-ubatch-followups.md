# 2026-06-23 16:57Z: Fast Top-K VMM/Ubatch Follow-Ups

Goal: try to beat the current single-B70 Gemma 4 26B A4B Q8 filled-long
record by combining the approved fast top-k MTP recipe with the best recent
wall/TTFT knobs.

Current record:

- `91.61894213332073 tok/s` after TTFT;
- `384/384` chat canary;
- LocalMaxxing `cmqqsecuk01azqo018ahv0i1s`;
- run:
  `data/gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-repeat-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T150833Z/summary.json`.

Common identity:

- llama.cpp `c926ad098`, SYCL AOT BMG build;
- model: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft model: `mtp-gemma-4-26B-A4B-it.gguf`;
- one full model replica per B70;
- `MTP_N_MAX=7`, `MTP_N_MIN=2`, `MTP_P_MIN=0.12`;
- `MTP_BACKEND_SAMPLING=0`;
- `MTP_DRAFT_THREADS=32`, `MTP_DRAFT_THREADS_BATCH=32`;
- `MTP_DRAFT_FAST_TOPK=1`;
- `MTP_EXTRA_ARGS='--ctx-checkpoints 0'`;
- `BENCH_PROMPT_MODE=filled-long`, `PROMPT_TOKENS=512`, `MAX_TOKENS=512`;
- validation: `CANARY_REPEATS=96` -> `384/384` chat rows.

## Results

| Variant | Gate | tok/s after TTFT | Wall tok/s | TTFT ms | Delta vs record | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `ctx4096 + ub512 + VMM=0 + top_k=10` | 384/384 | 91.426441 | 82.138882 | 636.308 | -0.192501 | valid loss; best wall/TTFT lane |
| `ub1024 + VMM=0 + top_k=10` | 384/384 | 91.165560 | 81.798516 | 645.969 | -0.453382 | valid loss |
| `ub512 + VMM=0 + top_k=9` | 384/384 | 90.838756 | 81.643350 | 637.477 | -0.780186 | valid loss |
| `ub512 + VMM=0 + top_k=10` repeat | 384/384 | 90.802460 | 81.610302 | 637.798 | -0.816482 | valid loss |

Artifacts:

- `data/gemma4-q8-gpu2-mtp-n7-c926-fasttopk10-vmm0-ctx4096ub512-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T165701Z/summary.json`
- `data/gemma4-q8-gpu1-mtp-n7-c926-fasttopk10-vmm0-ub1024-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T165701Z/summary.json`
- `data/gemma4-q8-gpu3-mtp-n7-c926-fasttopk9-vmm0-ub512-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T165701Z/summary.json`
- `data/gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-vmm0-ub512-repeat2-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T165701Z/summary.json`

Decision:

- No LocalMaxxing submission. All lanes were valid but below the existing
  after-TTFT record.
- `ctx4096 + ub512 + VMM=0` remains useful for wall throughput and TTFT
  reference work (`~82.14 tok/s` wall, `~636 ms` TTFT), but it is not the
  decode-record lane.
- Further flag-only work around ubatch/VMM/top-k is unlikely to produce a large
  decode win; move back to measured source-level MTP draft-loop work.
