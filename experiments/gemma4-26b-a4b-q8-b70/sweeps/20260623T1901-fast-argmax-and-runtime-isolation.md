# 2026-06-23T1901 Fast-Argmax And Runtime-Isolation Sweep

Goal: test whether bypassing the draft top-k probability path with a pure
argmax candidate improves the current valid fresh-response Gemma 4 26B A4B Q8
draft-MTP record, then isolate the VMM/ubatch/poll runtime knobs that improved
wall latency in earlier near-misses.

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
- `MTP_DRAFT_THREADS=32`, `MTP_DRAFT_THREADS_BATCH=32`;
- `MTP_EXTRA_ARGS='--ctx-checkpoints 0'`;
- `BENCH_PROMPT_MODE=filled-long`, `PROMPT_TOKENS=512`, `MAX_TOKENS=512`;
- `CANARY_REPEATS=96`, `BENCH_REPEATS=8`;
- `GGML_SYCL_DISABLE_OPT=0`, `FLASH_ATTN=off`, `THREADS=16`;
- draft-model MTP only; no draftless n-gram/history acceleration.

Fresh-response validity:

- all lanes use the Gemma MTP draft model, which can operate on a fresh request;
- context checkpoints are disabled and server `--cache-ram 0` is retained;
- `cached_tokens=0` in benchmark usage rows;
- first request is recorded separately from the repeat mean;
- no LocalMaxxing submission is made from warmed/history n-gram artifacts.

## Source Patch

Patch snapshot:
`patches/gemma4-llamacpp-mtp-draft-fast-argmax-20260623.patch`.

This is a combined research delta on top of upstream llama.cpp `c926ad098`. It
includes the earlier fast-top-k/profiling work plus the new gated
`LLAMA_MTP_DRAFT_FAST_ARGMAX=1` path. The new argmax path:

- calls `llama_synchronize(params.ctx_dft)`;
- reads `llama_get_logits_ith(params.ctx_dft, idx)`;
- scans the full vocab once for the max logit;
- returns a size-1 `llama_token_data_array` with probability `1.0`.

Hypothesis: the record fast-top-k lane had `p-min` stops at zero and very high
top-1 probabilities, so the top-k softmax/probability computation may be wasted
CPU overhead. Argmax should preserve target verification and quality while
removing the top-k insertion/probability work.

## Fast-Argmax Results

All four lanes passed the full canary. The best argmax mean technically edged
the record by `0.004889 tok/s`, but that is far inside run variance
(`~0.75 tok/s` stdev), so it is **not promoted** and was not submitted.

| Variant | Gate | First request tok/s | Mean tok/s after TTFT | Wall tok/s | TTFT ms | Delta vs record | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| argmax, default runtime, `p-min=0.12` | 384/384 | 91.459087 | 91.428685 | 71.184225 | 1594.061 | -0.190257 | valid loss |
| argmax, `VMM=0`, `UBATCH_SIZE=512`, `POLL=100`, `p-min=0.12` | 384/384 | 91.459087 | 91.623831 | 82.223946 | 641.093 | +0.004889 | valid noise-level near-tie; not promoted |
| argmax, default runtime, `p-min=0` | 384/384 | 91.144987 | 91.551250 | 71.176263 | 1590.785 | -0.067693 | valid loss |
| argmax, `VMM=0`, `UBATCH_SIZE=512`, `POLL=100`, `p-min=0` | 384/384 | 91.460273 | 91.247610 | 82.010687 | 639.518 | -0.371332 | valid loss |

Artifacts:

- `data/gemma4-q8-gpu0-mtp-n7-c926-fastargmax-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T190135Z/summary.json`
- `data/gemma4-q8-gpu1-mtp-n7-c926-fastargmax-vmm0-ub512-poll100-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T190135Z/summary.json`
- `data/gemma4-q8-gpu2-mtp-n7-c926-fastargmax-pmin0-ctxcp0-nmin2-nobs-dthreads32-dtb32-filled-long-deep-20260623T190135Z/summary.json`
- `data/gemma4-q8-gpu3-mtp-n7-c926-fastargmax-vmm0-ub512-poll100-pmin0-ctxcp0-nmin2-nobs-dthreads32-dtb32-filled-long-deep-20260623T190135Z/summary.json`

Decision:

- Keep the patch snapshot for future source work, but do not promote argmax.
- The full-vocab scan remains the same order of work as fast top-k, and the
  removed probability math is too small to move the sustained decode record.
- `VMM=0 + UBATCH_SIZE=512 + POLL=100` remains useful for wall/TTFT, not for
  after-TTFT decode.

## Fast-Top-K Runtime Isolation Results

This second batch kept the prior record draft path:
`LLAMA_MTP_DRAFT_FAST_TOPK=1`, `LLAMA_MTP_DRAFT_TOP_K=10`,
`MTP_P_MIN=0.12`.

| Variant | Gate | First request tok/s | Mean tok/s after TTFT | Wall tok/s | TTFT ms | Delta vs record | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| exact fast-top-k repeat | 384/384 | 90.741990 | 90.497017 | 70.617029 | 1592.729 | -1.121925 | valid repeat loss |
| `VMM=0`, `UBATCH_SIZE=512`, `POLL=100` | 384/384 | 90.622489 | 91.500244 | 82.156622 | 639.242 | -0.118698 | valid loss; good wall/TTFT |
| `UBATCH_SIZE=512`, `POLL=100`, VMM default | 384/384 | 90.481411 | 90.476432 | 81.397440 | 633.403 | -1.142510 | valid loss |
| `VMM=0`, `UBATCH_SIZE=512`, `POLL=50` | 384/384 | 90.822220 | 91.184612 | 81.983044 | 632.385 | -0.434330 | valid loss |

Artifacts:

- `data/gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-repeat2-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T190630Z/summary.json`
- `data/gemma4-q8-gpu1-mtp-n7-c926-fasttopk10-vmm0-ub512-poll100-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T190630Z/summary.json`
- `data/gemma4-q8-gpu2-mtp-n7-c926-fasttopk10-ub512-poll100-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T190630Z/summary.json`
- `data/gemma4-q8-gpu3-mtp-n7-c926-fasttopk10-vmm0-ub512-poll50-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T190630Z/summary.json`

Decision:

- No LocalMaxxing submission. All lanes preserved quality but missed the
  promoted `91.618942 tok/s` mean-after-TTFT record.
- The `VMM=0 + UBATCH_SIZE=512` family consistently lowers TTFT from about
  `1.59s` to about `0.63s` and improves wall throughput to about `82 tok/s`,
  but it does not improve sustained after-TTFT decode enough to promote.
- The exact repeat loss confirms the current record is a real high-water mark,
  not the center of the distribution.

## Profile Takeaway

Profile evidence from
`data/gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-profile-v2-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-smoke-20260623T171831Z/server.stdout.log`:

- benchmark requests accepted about `445/462` drafted tokens;
- mean acceptance length was about `7.74` with `n_max=7`;
- `p-min` stops were zero and top-1 probability averaged about `0.996`;
- cumulative draft work across two benchmark requests was about
  `draft_decode_ms=1689.599`, `fast_scan_ms=145.708`, `fast_prob_ms=0.325`;
- per request, deleting the whole fast-top-k scan/probability path is therefore
  only a small fraction of the total `~5.58s` decode time.

Conclusion: the current valid fresh-response MTP path is no longer acceptance
limited and is not meaningfully top-k limited. The next serious paths are:

1. vLLM/XPU INT8-per-channel comparison once the official HF checkpoint finishes
   downloading;
2. target verification / graph / kernel work that reduces the main-model cost
   per verified chunk;
3. transport of the draft argmax/candidates from device output without a full
   host-side vocab scan, but only if profiling shows it affects target-runtime
   overlap.

Do not spend more GPU time on small `top_k`, `p-min`, draft-thread, VMM, ubatch,
or poll sweeps under this exact llama.cpp MTP identity unless a source change
first moves the bottleneck.
