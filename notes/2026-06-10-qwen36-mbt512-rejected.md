# Qwen3.6 INT8 MBT512 Rejection

Date: 2026-06-10

## Context

I tested lowering `--max-num-batched-tokens` from `8192` to `512` while
keeping `--max-num-seqs 48`.

The intent was to see whether a smaller compile/scheduler token budget would
reduce decode graph replay overhead without changing model math.

Everything else stayed unchanged:

- model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- runtime dtype: BF16
- quantization: Quark W8A8 INT8
- tensor parallelism: TP4
- context cap: 32K
- XPU PIECEWISE graph capture
- clone-safe custom-op all-reduce collectives
- prefix caching disabled

The candidate kept chunked prefill enabled, so the 32K context cap remained
available. The compile range changed from `(1, 8192)` to `(1, 512)`.

## Runtime Behavior

The candidate compiled and served successfully:

- compile range: `(1, 512)`
- effective KV cache block size: `64`
- effective attention block size: `576`
- mamba page padding: `9.92%`
- GPU KV cache size: `2,080,768` tokens
- max 32K concurrency estimate: `63.50x`

This is slightly more reported KV-token capacity than the accepted no-prefix
runtime, but the compile time was not materially improved because this still
requires a fresh graph/AOT path.

## Single Request Result

p512/n512 streaming, eight repeats:

| metric | no-prefix baseline | MBT512 |
| --- | ---: | ---: |
| corrected output tok/s after first chunk | `98.0404` | `98.1973` |
| output tok/s end-to-end | `96.7747` | `96.9600` |
| mean client TTFT | `77.74 ms` | `76.72 ms` |

Artifacts:

- baseline: `data/qwen36-quark-int8-tp4-noprefix-graph32k-single-confirm-20260610.json`
- candidate: `data/qwen36-quark-int8-tp4-noprefix-mbt512-graph32k-single-20260610.json`

The single-request result is effectively flat. It does not clear the bar for a
meaningful speed promotion.

## Aggregate Result

Frontdoor p512/n256 sweep:

| concurrency | no-prefix wall tok/s | MBT512 wall tok/s | no-prefix from-first tok/s | MBT512 from-first tok/s |
| --- | ---: | ---: | ---: | ---: |
| 1 | `95.94` | `95.85` | `99.02` | `99.32` |
| 2 | `170.19` | `166.51` | `181.10` | `171.88` |
| 4 | `307.85` | `313.03` | `316.24` | `328.74` |
| 8 | `553.27` | `524.05` | `566.10` | `545.90` |
| 16 | `851.63` | `485.89` | `868.43` | `494.74` |
| 32 | `1397.95` | `1186.64` | `1419.06` | `1208.69` |
| 48 | `1700.89` | `1351.21` | `1727.50` | `1366.53` |

Artifacts:

- baseline: `data/qwen36-quark-int8-tp4-noprefix-graph32k-concurrency-20260610.json`
- candidate: `data/qwen36-quark-int8-tp4-noprefix-mbt512-graph32k-concurrency-20260610.json`

The candidate regresses c48 wall throughput by about `20.6%` and c16 wall
throughput by about `42.9%`.

## Decision

Reject `--max-num-batched-tokens 512` for this Qwen3.6 INT8 stack. It is
quality-neutral in principle, but it does not materially improve single-request
decode and it badly hurts aggregate throughput for the current frontdoor
workload.

Keep `--max-num-batched-tokens 8192` for the current no-prefix runtime.
