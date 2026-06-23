# 2026-06-23T2011 Spec-Verify Greedy Argmax Smoke

Goal: reduce fresh-response draft-MTP target verification overhead by bypassing
the general CPU sampler for deterministic greedy verifier rows.

Patch snapshot:
`patches/gemma4-llamacpp-spec-verify-greedy-argmax-20260623.patch`.

The patch adds gated `LLAMA_SPEC_VERIFY_GREEDY_ARGMAX=1` behavior in
`common/sampling.cpp`. When active, `common_sampler_sample_and_accept_n()`
synchronizes once, scans target logits for argmax across verifier rows, accepts
tokens through the normal sampler history, and stops on the first draft
mismatch. It falls back unless the request is greedy-equivalent:

- explicit env flag enabled;
- `temp <= 0`;
- no grammar or reasoning-budget sampler;
- no logprobs, logit bias, ignore-eos, penalties, DRY, XTC, mirostat, adaptive
  sampling, or dynamic temperature.

This is a fresh-response patch, not n-gram/history acceleration.

## Smoke Result

Compared against current promoted fresh-response record:

- record: `91.618942 tok/s` after TTFT, first request `91.251146`, 384/384;
- record artifact:
  `data/gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-repeat-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T150833Z/summary.json`.

Smoke identity:

- llama.cpp `c926ad098`, SYCL AOT BMG build;
- target: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: `mtp-gemma-4-26B-A4B-it.gguf`;
- `MTP_N_MAX=7`, `MTP_N_MIN=2`, `MTP_P_MIN=0.12`;
- `LLAMA_MTP_DRAFT_FAST_TOPK=1`, `LLAMA_MTP_DRAFT_TOP_K=10`;
- backend draft sampling off;
- `MTP_EXTRA_ARGS='--ctx-checkpoints 0'`;
- `LLAMA_SPEC_VERIFY_GREEDY_ARGMAX=1`;
- `BENCH_PROMPT_MODE=filled-long`, `PROMPT_TOKENS=512`, `MAX_TOKENS=512`;
- `CANARY_REPEATS=32`, `BENCH_REPEATS=4`.

| Gate | Mean after TTFT | Best request | Wall tok/s | TTFT s | Decision |
| ---: | ---: | ---: | ---: | ---: | --- |
| 128/128 | 91.550284 | 92.908568 | 71.139933 | 1.604630 | valid smoke loss; do not promote |

Artifact:

- `data/gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-verifyargmax-smoke-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T201141Z/summary.json`

## Interpretation

The patch preserves canary quality in a 128-row smoke but does not clear the
current record. That supports Dirac's audit: CPU verifier sampling work exists,
but this patch still pays full target decode and full-vocab logits transfer for
each verifier row. It may be useful as a component if a future patch avoids
logits materialization or backend multi-row sampling becomes available, but by
itself it is not enough to justify a full 384-row gate or LocalMaxxing
submission.

Next action: pivot to vLLM/XPU int8-per-channel once the official HF snapshot
finishes downloading.

## Runtime Interaction Smoke: VMM Off + Larger UBatch + Fast Poll

Follow-up identity:

- same verifier-argmax patch and Gemma Q8 MTP recipe as above;
- `GPU_INDEX=2`, `GGML_SYCL_ENABLE_VMM=0`;
- `UBATCH_SIZE=512`, `POLL=100`;
- `CANARY_REPEATS=32`, `BENCH_REPEATS=4`.

| Gate | Mean after TTFT | Best request | Wall tok/s | TTFT s | Decision |
| ---: | ---: | ---: | ---: | ---: | --- |
| 128/128 | 91.375858 | 91.434804 | 81.632818 | 0.672061 | valid smoke loss; do not promote |

Artifact:

- `data/gemma4-q8-gpu2-mtp-n7-c926-fasttopk10-verifyargmax-vmm0-ub512-poll100-smoke-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T201741Z/summary.json`

Interpretation: the runtime knobs improve wall-rate and TTFT for this short
smoke, but they do not improve the headline after-TTFT fresh decode rate. The
result is useful as a latency/serving interaction note, not a LocalMaxxing
record candidate. The conclusion remains unchanged: verifier sampler bypass is
not the limiting factor for the current fresh MTP lane.
