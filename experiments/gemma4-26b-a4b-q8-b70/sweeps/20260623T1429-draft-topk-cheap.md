# Draft MTP top-k cheap sweep

Date: 2026-06-23
Owner/agent: Codex
GPU / ports: GPUs 0-3, ports 18470-18473

## Hypothesis

The prior raw-prob draft top-k patch preserved full-softmax `p_min`
semantics, but that added a full-vocab probability recomputation and lost
throughput. This sweep kept the useful part only: expose the MTP draft sampler
`top_k` as an env var, but leave stock llama.cpp probability semantics intact
(probabilities normalized over the filtered top-k candidate set).

This is a quality-risk experiment because smaller `top_k` can make the winning
draft token look more confident to the `p_min=0.12` gate. The verifier still
guards final output, so promotion requires full `384/384` chat canaries.

## Patch

Archived patch:

- `patches/gemma4-llamacpp-mtp-draft-topk-env-cheap-20260623.patch`

Patch behavior:

- adds `LLAMA_MTP_DRAFT_TOP_K` with alias `LLAMA_SPEC_DRAFT_MTP_TOP_K`;
- keeps default behavior at `top_k=10`;
- applies the env value only in `common_speculative_impl_draft_mtp`;
- intentionally does **not** rescale candidate probabilities against the raw
  full-vocab softmax.

The local llama.cpp source was built from `c926ad098`, version `9769`, with this
patch applied.

## Run Identity

Unless noted otherwise:

- model: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft: `mtp-gemma-4-26B-A4B-it.gguf`
- runtime: llama.cpp SYCL AOT BMG build, `c926ad098` + local cheap top-k patch
- GPU: one Intel Arc Pro B70 per run
- context / batch / ubatch: `8192 / 512 / 64`
- KV cache dtype: f16/f16, draft f16/f16
- prompt: `BENCH_PROMPT_MODE=filled-long`, usage-derived `588` prompt / `512`
  completion tokens
- validation: `CANARY_REPEATS=96` over four chat-canary cases (`384/384`)
- benchmark: `BENCH_REPEATS=8`
- base MTP flags: `MTP_N_MAX=7`, `MTP_N_MIN=2`, `MTP_P_MIN=0.12`,
  `MTP_BACKEND_SAMPLING=0`, `MTP_DRAFT_THREADS=32`,
  `MTP_DRAFT_THREADS_BATCH=32`, `MTP_EXTRA_ARGS='--ctx-checkpoints 0'`

Current valid record for comparison:

- `gemma4-q8-gpu0-mtp-n7-latest-c926ad098-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T113058Z`
- `91.15671739968305 tok/s` after TTFT, `384/384` canary

## Result

All lanes passed the full canary gate, but no lane beat the record.

| Label suffix | `LLAMA_MTP_DRAFT_TOP_K` | GPU | canary | after-TTFT tok/s | wall tok/s | TTFT ms | best repeat tok/s | vs record |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `drafttopk1-cheap` | `1` | 0 | `384/384` | `90.626387` | `70.717683` | `1590.506` | `90.922876` | `-0.530330` |
| `drafttopk2-cheap` | `2` | 1 | `384/384` | `90.911027` | `70.804866` | `1599.302` | `92.202710` | `-0.245691` |
| `drafttopk4-cheap` | `4` | 2 | `384/384` | `89.893069` | `70.169200` | `1601.071` | `90.160331` | `-1.263648` |
| `drafttopk10-cheap` | `10` | 3 | `384/384` | `90.170499` | `70.332651` | `1601.617` | `91.071885` | `-0.986218` |

## Decision

Loss. Do not promote or submit to LocalMaxxing. The cheap top-k hook itself is
valid and low-risk as an experiment control, but top-k selection did not
recover enough speed to beat the existing record.

The top-k 2 lane is the closest (`90.911027`, about `0.246 tok/s` below record)
and had one fast repeat above record (`92.202710`), but promotion is by mean
after-TTFT with full validation, not best repeat.

## Follow-up

The next source-level idea should keep this top-k hook available and add a
separate env-gated logit-gap/top-1 confidence filter inside
`common_speculative_impl_draft_mtp::draft()`, after candidate sorting and before
the existing `p_min` check. That would use only the already available top-k
logits and avoid a full-vocab softmax, while potentially rejecting ambiguous
draft steps more cheaply than the current normalized top-k probability gate.

Keep it as a separate patch/result note so it can be attributed independently.

## Artifacts

- `data/gemma4-q8-gpu0-mtp-n7-c926-drafttopk1-cheap-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T142927Z/`
- `data/gemma4-q8-gpu1-mtp-n7-c926-drafttopk2-cheap-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T142927Z/`
- `data/gemma4-q8-gpu2-mtp-n7-c926-drafttopk4-cheap-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T142927Z/`
- `data/gemma4-q8-gpu3-mtp-n7-c926-drafttopk10-cheap-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T142927Z/`
- server logs under
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/*20260623T142927Z.server.log`
