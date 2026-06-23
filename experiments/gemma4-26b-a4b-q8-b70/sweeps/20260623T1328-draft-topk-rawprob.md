# Draft MTP top-k raw-prob sweep

Date: 2026-06-23
Owner/agent: Codex
GPU / port: GPUs 0-3, ports 18460-18463

## Hypothesis

The current best valid Gemma 4 26B A4B Q8 lane uses llama.cpp `c926ad098`,
draft-MTP n=7, `n_min=2`, `p_min=0.12`, no draft backend sampling, 32 draft
threads, 32 draft batch threads, and `--ctx-checkpoints 0`.

`common/speculative.cpp` hardcodes draft-MTP sampler `top_k=10`. Earlier timing
work showed draft-side sampling/selection is part of the remaining overhead, so
this experiment exposed the draft-MTP `top_k` as an environment variable and
tested `top_k=1/2/4/10`.

The patch also preserved `p_min` semantics after top-k truncation by rescaling
the selected draft candidates against the full raw-logit softmax denominator.
This was intentionally conservative for quality: a naive top-k sampler would
renormalize within the truncated set and could make a low-probability token look
like `p=1.0`.

## Patch

Archived patch:

- `patches/gemma4-llamacpp-mtp-draft-topk-env-rawprob-20260623.patch`

Patch behavior:

- adds `LLAMA_MTP_DRAFT_TOP_K` (alias `LLAMA_SPEC_DRAFT_MTP_TOP_K`) with default
  `10`;
- routes both CPU and backend draft-MTP samplers through that value;
- adds `common_sampler_rescale_candidates_to_logits_probs(...)` and uses it for
  MTP candidate probabilities so `p_min` is evaluated against the full draft
  logits distribution.

The harness now records and forwards `LLAMA_MTP_DRAFT_TOP_K` so future source
patches can be attributed in run summaries.

## Run Identity

- model repo: Unsloth Gemma 4 26B A4B IT GGUF
- filename: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- file bytes: `27636230944`
- draft model: `mtp-gemma-4-26B-A4B-it.gguf`
- runtime: llama.cpp SYCL AOT BMG build
- runtime commit/version: `c926ad098`, version `9769`
- backend: Intel oneAPI Level Zero / SYCL, single B70 per run
- context: `8192`
- batch / ubatch: `512` / `64`
- KV cache dtype: f16/f16
- API mode: OpenAI-compatible `llama-server`, `--parallel 1 --cache-ram 0`
- prompt: `BENCH_PROMPT_MODE=filled-long`, usage-derived `588` prompt / `512`
  completion tokens
- validation: `CANARY_REPEATS=96` over four chat-canary cases (`384/384`)
- benchmark: `BENCH_REPEATS=8`
- base MTP flags: `MTP_N_MAX=7`, `MTP_N_MIN=2`, `MTP_P_MIN=0.12`,
  `MTP_BACKEND_SAMPLING=0`, `MTP_DRAFT_THREADS=32`,
  `MTP_DRAFT_THREADS_BATCH=32`, `MTP_EXTRA_ARGS='--ctx-checkpoints 0'`

## Result

Current valid record for comparison:

- `gemma4-q8-gpu0-mtp-n7-latest-c926ad098-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T113058Z`
- `91.15671739968305 tok/s` after TTFT, `384/384` canary

All raw-prob top-k runs passed the full `384/384` canary gate, but all lost
speed relative to the record:

| label suffix | `LLAMA_MTP_DRAFT_TOP_K` | GPU | canary | after-TTFT tok/s | wall tok/s | TTFT s | best repeat tok/s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `drafttopk1-rawprob` | `1` | 0 | `384/384` | `86.295105` | `68.005339` | `1.595697` | `88.031134` |
| `drafttopk2-rawprob` | `2` | 1 | `384/384` | `86.829947` | `68.288798` | `1.601003` | `88.164954` |
| `drafttopk4-rawprob` | `4` | 2 | `384/384` | `86.588181` | `68.167064` | `1.598009` | `86.742985` |
| `drafttopk10-rawprob` | `10` | 3 | `384/384` | `86.150719` | `67.854000` | `1.602537` | `86.381344` |

## Decision

Loss. The quality-preserving raw-probability rescale is too expensive and/or
too strict for this lane. Lowering `top_k` does not recover the overhead; the
best mean (`top_k=2`, `86.829947`) remains about `4.327 tok/s` below the
promoted `91.156717` record.

Do not promote this patch or submit it to LocalMaxxing. Keep it as a failed
source-level artifact because it proves that conservative raw-prob preservation
is not the cheap sampler win.

## Follow-up

If sampler work is revisited, try a cheaper experiment separately:

- configurable `top_k` without full raw-softmax rescale, treated as a quality
  risk and gated by deeper canaries; or
- optimized denominator / approximate top-1 confidence that does not touch the
  full vocab every draft step.

The next higher-signal path is model/draft-model identity, especially testing
the local `gemma-4-26B-A4B-it-assistant.Q8_0.gguf` assistant against the
current default `mtp-gemma-4-26B-A4B-it.gguf`.

## Artifacts

- `data/gemma4-q8-gpu0-mtp-n7-latest-c926ad098-drafttopk1-rawprob-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T132852Z/`
- `data/gemma4-q8-gpu1-mtp-n7-latest-c926ad098-drafttopk2-rawprob-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T132852Z/`
- `data/gemma4-q8-gpu2-mtp-n7-latest-c926ad098-drafttopk4-rawprob-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T132852Z/`
- `data/gemma4-q8-gpu3-mtp-n7-latest-c926ad098-drafttopk10-rawprob-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T132852Z/`
- server logs under
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/*20260623T132852Z.server.log`
