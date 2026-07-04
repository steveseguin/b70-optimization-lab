# Qwen27 Record Stack 4-GPU Verify Trace

Date: 2026-07-04

Status: **diagnostic-only support**, no LocalMaxxing submission.

## Purpose

Run the current Qwen27 strict record stack across all four B70 GPUs in the same
window with compact verifier traces enabled. The goal was to determine whether
recent below-record rows were caused by lower draft acceptance or by runtime /
GPU variance, and whether there is a credible per-prompt acceptance policy worth
patching.

This is not a new optimization and not a record attempt. Every row used the
fixed Qwen realistic suite, each prompt once, `cached_tokens=0`, token-ID timing,
and target-verified MTP.

## Shared Identity

- Model: `webhie/Qwen3.6-27B-int4-AutoRound`
- Snapshot: `f5750c90b3776db658594df5fe8051098226dd8e`
- Runtime: vLLM/XPU, one B70 per run, TP1
- Recipe: runtime INT8 LM-head with BF16 scales, MTP3, cg8
- Key env:
  `VLLM_XPU_LM_HEAD_INT8=1`,
  `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16`,
  `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1`,
  `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`
- Stamp: `20260704T110712Z`

## Results

| GPU | Gate | Median tok/s | P10 | Mean | TTFT median | Target tokens/step | Prefix accept | Full accept |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| `0` | pass, `cached_tokens=0` | `64.180` | `56.605` | `63.049` | `615.7 ms` | `2.7950` | `0.5983` | `0.4046` |
| `1` | pass, `cached_tokens=0` | `63.893` | `56.171` | `62.546` | `621.8 ms` | `2.7900` | `0.5967` | `0.4057` |
| `2` | pass, `cached_tokens=0` | `62.633` | `51.983` | `59.032` | `623.3 ms` | `2.7851` | `0.5950` | `0.4032` |
| `3` | pass, `cached_tokens=0` | `63.181` | `56.426` | `62.753` | `617.5 ms` | `2.7900` | `0.5967` | `0.4057` |

The speed spread was `2.44%` of the four-GPU mean, but acceptance was almost
identical: target-verified tokens per step ranged only `2.7851-2.7950`.

Compact combined summary:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-recordstack-verifytrace4gpu-acceptance-20260704T110712Z-summary.json
```

Per-run result and verifier summaries:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-recordstack-verifytrace4gpu-gpu0-20260704T110712Z-20260704T110712Z.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-recordstack-verifytrace4gpu-gpu0-20260704T110712Z-verify-summary.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-recordstack-verifytrace4gpu-gpu1-20260704T110712Z-20260704T110712Z.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-recordstack-verifytrace4gpu-gpu1-20260704T110712Z-verify-summary.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-recordstack-verifytrace4gpu-gpu2-20260704T110712Z-20260704T110712Z.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-recordstack-verifytrace4gpu-gpu2-20260704T110712Z-verify-summary.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-recordstack-verifytrace4gpu-gpu3-20260704T110712Z-20260704T110712Z.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-recordstack-verifytrace4gpu-gpu3-20260704T110712Z-verify-summary.json
```

Raw verifier traces live under the run dirs in `/mnt/fast-ai/bench-results/`
and were not copied into Git.

## Interpretation

This window did not reproduce the promoted `65.27648650325429 tok/s` record.
The best row was `64.180 tok/s`, so there is no record submission.

The important finding is that acceptance was stable across GPUs while speed
varied. That means this particular below-record window is not explained by poor
draft quality or prompt-specific acceptance collapse. It is runtime/GPU variance
plus normal run noise.

Lowest aggregate acceptance prompts remain consistent with previous traces:
`performance-hypotheses`, `customer-email`, `release-plan`, `code-review`,
`decision-memo`, and `technical-guide`. However, because all GPUs saw almost the
same acceptance rates, a scheduler-only or prompt-policy acceptance heuristic is
unlikely to recover throughput. Prior adaptive-depth tests already confirmed
that reducing verifier depth lowers emitted tokens per step and loses.

## Decision

Do not promote, submit, or rerun this as a record path. Use it as support for
the next-lane choice:

1. a real LM-head top-ID producer that reduces draft and target full-vocab work;
2. a materially stronger target-matched drafter, trained/evaluated on held-out
   non-final data;
3. DFlash mixed-SWA only after proper multi-KV drafter metadata support exists.

Avoid more scheduler-only acceptance heuristics, MTP-depth config sweeps, or
per-prompt policy changes without a new source mechanism that preserves emitted
tokens per verifier step.
