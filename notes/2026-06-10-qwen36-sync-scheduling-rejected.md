# Qwen3.6 INT8 Sync Scheduling Rejection

Date: 2026-06-10

## Context

I tested `--no-async-scheduling` on the accepted Qwen3.6 INT8 no-prefix
runtime.

The intent was to see whether disabling vLLM V1 async scheduling would reduce
single-request host/scheduler overhead. This does not change model weights,
quantization, sampling math, tensor parallelism, or graph-captured model
execution.

Everything else stayed unchanged:

- model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- runtime dtype: BF16
- quantization: Quark W8A8 INT8
- tensor parallelism: TP4
- context cap: 32K
- XPU PIECEWISE graph capture
- clone-safe custom-op all-reduce collectives
- prefix caching disabled
- `--max-num-batched-tokens 8192`
- `--max-num-seqs 48`

The runtime log confirmed `Asynchronous scheduling is disabled`.

## Single Request Result

p512/n512 streaming, eight repeats:

| metric | no-prefix baseline | sync scheduling |
| --- | ---: | ---: |
| corrected output tok/s after first chunk | `98.0404` | `96.1697` |
| output tok/s end-to-end | `96.7747` | `95.0073` |
| total client tok/s | `194.6544` | `190.0147` |
| mean client TTFT | `77.74 ms` | `75.53 ms` |

Artifacts:

- baseline: `data/qwen36-quark-int8-tp4-noprefix-graph32k-single-confirm-20260610.json`
- candidate: `data/qwen36-quark-int8-tp4-noprefix-syncsched-graph32k-single-20260610.json`

The candidate improves TTFT by roughly `2.2 ms`, but regresses corrected
single-request decode by about `1.9%`.

## Decision

Reject `--no-async-scheduling` for this Qwen3.6 INT8 runtime.

Keep the accepted default async scheduling path because the current priority is
single-request decode speed, and the TTFT improvement is too small to justify
the output-token regression.
