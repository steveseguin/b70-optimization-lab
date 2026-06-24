# 2026-06-23T2325 - Rebuild control, cross-GPU split, and MTP depth smokes

Goal: validate that the rebuilt llama.cpp Gemma source still reproduces the
current record lane, test whether target/draft split across two B70 GPUs is
viable, and re-check whether deeper draft-MTP lengths improve fresh-response
throughput.

Fresh-response validity: all benchmark rows below used `BENCH_REPEATS=1`, so
the throughput number is the first measured request after canaries. These are
smokes, not promoted records.

Current valid fresh-response record to beat:

- label:
  `gemma4-q8-gpu0-mtp-n7-c926-fastargmax-cpucleanup-vmm0-ub512-poll100-full-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T222838Z`
- canary: `384/384`
- first measured request after TTFT: `92.39728860909672 tok/s`
- first measured wall throughput: `79.19332242673484 tok/s`
- repeated mean after TTFT: `92.76706524545781 tok/s`
- every benchmark row reported `cached_tokens=0`

## Rebuild Control

The active llama.cpp source tree at commit `c926ad098` was rebuilt in
`/home/steve/src/llama.cpp-latest-gemma/build-sycl-b70-aot-bmg-g31` after
confirming the lazy verifier patch was no longer present.

Common knobs:

- model:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft model:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/mtp-gemma-4-26B-A4B-it.gguf`
- `GGML_SYCL_ENABLE_VMM=0`, `UBATCH_SIZE=512`, `POLL=100`
- `--spec-draft-n-max 7`, `--spec-draft-n-min 2`, `--spec-draft-p-min 0.12`
- `--no-spec-draft-backend-sampling`, `--ctx-checkpoints 0`
- `LLAMA_MTP_DRAFT_FAST_ARGMAX=1`, `LLAMA_MTP_DRAFT_FAST_TOPK=0`
- `MTP_DRAFT_THREADS=32`, `MTP_DRAFT_THREADS_BATCH=32`
- `CANARY_REPEATS=16` (`64/64` rows), `BENCH_REPEATS=1`,
  `BENCH_PROMPT_MODE=filled-long`

| Label suffix | GPU | Profile | Canary | First request after-TTFT tok/s | Wall tok/s | Decision |
| --- | ---: | --- | ---: | ---: | ---: | --- |
| `rebuild-control-profile-smoke` | 0 | on | 64/64 | `91.64941645777418` | `78.63392056727398` | reproduces current lane, below record |
| `rebuild-control-noprofile-smoke` | 1 | off | 64/64 | `92.10904616931985` | `78.96154735164095` | close control, below record |

Profile from the profile smoke's 512-token row:

- `process_ms=6.114`
- `draft_decode_ms=1890.004`
- `fast_sync_ms=3.700`
- `fast_logits_ms=0.653`
- `fast_scan_ms=121.421`
- `hidden_get_ms=0.911`
- `handoff_ms=0.656`
- `accept_copy_ms=0.152`
- counts: `process_calls=325`, `verify_rows=4620`,
  `draft_decodes=1358`, `fast_topk_calls=1358`,
  `vocab_scanned=355991552`, `nmax stops=194`

Interpretation: source/host cleanup is not the main remaining bottleneck.
Draft decode dominates; vocab scan is second-order; verifier hidden-row copies
and handoff are negligible.

## Cross-GPU Target/Draft Split

Attempted to run target on `SYCL0` and draft on `SYCL1` inside
`ONEAPI_DEVICE_SELECTOR=level_zero:2,3`:

- label:
  `gemma4-q8-gpu2target-gpu3draft-mtp-n7-c926-crossgpu-smoke-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T2325Z`
- target device: `-dev SYCL0`
- draft device: `MTP_DRAFT_DEVICE=SYCL1`

The server failed before readiness:

```text
/home/steve/src/llama.cpp-latest-gemma/ggml/src/ggml-backend.cpp:898:
pre-allocated tensor (cache_v_l28) in a buffer (SYCL0) that cannot run the
operation (NONE)
```

Decision: cross-GPU target/draft split is not currently a viable optimization
lane for this Gemma llama.cpp MTP setup. It likely needs llama.cpp/backend
scheduler work around shared KV / device placement before it can be benchmarked.

## MTP Depth Recheck

Common knobs matched the rebuild control except `--spec-draft-n-max`.

| n_max | GPU | Canary | First request after-TTFT tok/s | Wall tok/s | Decision |
| ---: | ---: | ---: | ---: | ---: | --- |
| 6 | 0 | 64/64 | `86.77622982623186` | `74.8725254092122` | loss |
| 7 | 1 | 64/64 | `91.56885810786738` | `78.43587315569408` | best of this smoke, still below record |
| 8 | 2 | 64/64 | `62.06805417434111` | `55.82518782061592` | collapse |
| 10 | 3 | 64/64 | `70.11836598479617` | `62.215229215191066` | collapse |

Conclusion: deeper draft-MTP does not improve this lane. `n_max=7` remains the
best depth found so far. The profile says the >150 tok/s path cannot come from
another small host-side cleanup; it needs a change that materially reduces
draft decode work per accepted token or increases fresh-valid accepted tokens
without extra draft forwards.

