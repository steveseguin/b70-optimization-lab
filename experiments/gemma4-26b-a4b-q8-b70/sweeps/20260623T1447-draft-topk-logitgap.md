# Draft MTP top-k + logit-gap sweep

Date: 2026-06-23
Owner/agent: Codex
GPU / ports: GPUs 0-3, ports 18470-18473

## Hypothesis

The cheap `LLAMA_MTP_DRAFT_TOP_K` sweep showed `top_k=2` was the closest
source-level sampler variant, but it still missed the current record. This
follow-up added an env-gated logit-gap confidence stop after candidate sorting
and before the existing `p_min` gate:

- if `LLAMA_MTP_DRAFT_LOGIT_GAP_MIN > 0`;
- and the already-materialized top-2 draft logits differ by less than that
  threshold;
- stop drafting for that sequence.

The goal was to reject ambiguous low-margin draft steps without recomputing a
full-vocab softmax. The verifier still owns final output, but this changes draft
acceptance behavior, so every lane used the full `384/384` chat-canary gate.

## Patch

Archived patch:

- `patches/gemma4-llamacpp-mtp-draft-topk-logitgap-20260623.patch`

Patch behavior:

- keeps the prior `LLAMA_MTP_DRAFT_TOP_K` hook and alias;
- adds `LLAMA_MTP_DRAFT_LOGIT_GAP_MIN` with default `0.0` disabled;
- logs both knobs from llama.cpp startup;
- applies the logit-gap stop only in `common_speculative_impl_draft_mtp`.

Harness updates in this run:

- `scripts/run-gemma4-26b-mtp-candidate.sh` exports
  `MTP_DRAFT_LOGIT_GAP_MIN` as `LLAMA_MTP_DRAFT_LOGIT_GAP_MIN`;
- `scripts/run-gemma4-26b-llamacpp-replica.sh` logs it in the server header;
- `scripts/run-gemma4-26b-first-baseline.sh` records it in
  `summary.json -> launcher_identity.llama_mtp_draft_logit_gap_min`.

The local llama.cpp source was built from `c926ad098`, version `9769`, with this
patch applied.

## Run Identity

Unless noted otherwise:

- model: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft: `mtp-gemma-4-26B-A4B-it.gguf`
- runtime: llama.cpp SYCL AOT BMG build, `c926ad098` + local top-k/logit-gap patch
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
- source-gated sampler knobs: `MTP_DRAFT_TOP_K=2` plus the logit-gap threshold
  listed below.

Current valid record for comparison:

- `gemma4-q8-gpu0-mtp-n7-latest-c926ad098-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T113058Z`
- `91.15671739968305 tok/s` after TTFT, `384/384` canary

## Result

All lanes passed the full canary gate, but no lane beat the record.

| Label suffix | `LLAMA_MTP_DRAFT_TOP_K` | `LLAMA_MTP_DRAFT_LOGIT_GAP_MIN` | GPU | canary | after-TTFT tok/s | wall tok/s | TTFT ms | best repeat tok/s | vs record |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `topk2-logitgap025` | `2` | `0.25` | 0 | `384/384` | `90.483979` | `70.616411` | `1592.065` | `91.105241` | `-0.672739` |
| `topk2-logitgap050` | `2` | `0.50` | 1 | `384/384` | `90.309634` | `70.456680` | `1597.500` | `90.666121` | `-0.847084` |
| `topk2-logitgap100` | `2` | `1.00` | 2 | `384/384` | `90.467615` | `70.522337` | `1600.617` | `90.867243` | `-0.689102` |
| `topk2-logitgap150` | `2` | `1.50` | 3 | `384/384` | `90.148091` | `70.303111` | `1603.261` | `90.503329` | `-1.008627` |

Server logs confirmed the patch was active:

- `draft_top_k=2`
- `draft_logit_gap_min=0.250 / 0.500 / 1.000 / 1.500`

## Decision

Loss. Do not promote or submit to LocalMaxxing.

The logit-gap gate preserved correctness but did not improve mean throughput.
It appears to slightly reduce speed relative to the cheap `top_k=2` lane, which
had reached `90.911027 tok/s` without the logit-gap stop.

The source hook remains useful as a recorded experiment and can be reused for
diagnostics, but it should not be part of the promoted Gemma 4 Q8 recipe.

## Follow-up

Stop spending effort on tiny sampler-confidence thresholds for this identity.
The timing lane showed the real costs are MTP draft decode and sampler overhead,
not hidden-state handoff. The next useful lanes are:

1. source-level reduction of draft decode/sampler work, such as adaptive draft
   depth or cheaper direct top-1 MTP candidate handling;
2. a clean vLLM/XPU `int8_per_channel_weight_only` single-replica baseline for
   Gemma 4 26B A4B as a non-llama.cpp comparison;
3. 16K/32K context viability after speed work, not as a speed-record lane.

## Artifacts

- `data/gemma4-q8-gpu0-mtp-n7-c926-topk2-logitgap025-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T144714Z/`
- `data/gemma4-q8-gpu1-mtp-n7-c926-topk2-logitgap050-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T144714Z/`
- `data/gemma4-q8-gpu2-mtp-n7-c926-topk2-logitgap100-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T144714Z/`
- `data/gemma4-q8-gpu3-mtp-n7-c926-topk2-logitgap150-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T144714Z/`
- server logs under
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/*20260623T144714Z.server.log`
