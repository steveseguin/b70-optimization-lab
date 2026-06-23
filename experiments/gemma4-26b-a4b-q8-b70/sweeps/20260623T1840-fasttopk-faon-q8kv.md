# 2026-06-23 18:40Z: Fast Top-K With FA-On And Q8 KV Variants

Goal: test whether q8 KV cache variants reduce the draft-MTP decode bottleneck
under the current fast-top-k source identity. Earlier q8 draft-cache attempts
were before the promoted fast-top-k patch, so this batch retested them against
the current valid fresh-response record lane.

Current valid fresh-response record:

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
- `MTP_N_MAX=7`, `MTP_N_MIN=2`, `MTP_P_MIN=0.12`, backend sampling off;
- `LLAMA_MTP_DRAFT_FAST_TOPK=1`, `LLAMA_MTP_DRAFT_TOP_K=10`;
- `MTP_DRAFT_THREADS=32`, `MTP_DRAFT_THREADS_BATCH=32`;
- `MTP_EXTRA_ARGS='--ctx-checkpoints 0'`;
- `BENCH_PROMPT_MODE=filled-long`, `PROMPT_TOKENS=512`, `MAX_TOKENS=512`;
- `CANARY_REPEATS=96`, `BENCH_REPEATS=8`;
- `GGML_SYCL_DISABLE_OPT=0`, `THREADS=16`.

Fresh-response validity:

- draft-model MTP only; no n-gram/history acceleration;
- `--cache-ram 0` and `--ctx-checkpoints 0`;
- first request reported separately.

## Results

| Variant | Gate | First request tok/s | Mean tok/s after TTFT | Wall tok/s | TTFT ms | Delta vs record | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `FLASH_ATTN=on`, draft `K=f16,V=q8_0` | 384/384 | 91.700158 | 90.337112 | 70.224376 | 1623.058 | -1.281830 | valid loss |
| `FLASH_ATTN=on`, draft `K=q8_0,V=q8_0` | 384/384 | 90.033545 | 89.714858 | 69.742058 | 1634.337 | -1.904084 | valid loss |
| `FLASH_ATTN=on`, target `K=f16,V=q8_0`, draft `f16/f16` | 384/384 | 90.334769 | 90.108339 | 69.981941 | 1634.142 | -1.510603 | valid loss |
| `FLASH_ATTN=on`, draft `V=q8_0`, `VMM=0`, `UBATCH_SIZE=512` | 384/384 | 90.764864 | 90.398313 | 80.857171 | 669.491 | -1.220629 | valid loss; best wall in this batch |

Artifacts:

- `data/gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-faon-draftv-q8-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T184023Z/summary.json`
- `data/gemma4-q8-gpu1-mtp-n7-c926-fasttopk10-faon-draftkv-q8-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T184023Z/summary.json`
- `data/gemma4-q8-gpu2-mtp-n7-c926-fasttopk10-faon-targetv-q8-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T184023Z/summary.json`
- `data/gemma4-q8-gpu3-mtp-n7-c926-fasttopk10-faon-draftv-q8-vmm0ub512-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T184023Z/summary.json`

Decision:

- No LocalMaxxing submission. All variants passed the full canary gate but
  missed the promoted record by at least `1.22 tok/s`.
- `FLASH_ATTN=on` remains a net loss for the after-TTFT decode record even when
  q8 KV is combined with the fast-top-k source patch.
- Do not revisit draft q8 KV, target q8 V-cache, or FA-on+VMM/UB512 for this
  exact fast-top-k identity unless a new llama.cpp runtime changes FA/SYCL
  behavior.
